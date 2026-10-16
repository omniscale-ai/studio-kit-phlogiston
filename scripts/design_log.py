#!/usr/bin/env python3
"""Pre-registration log for DATASET batches (P5). Stdlib only.

    python3 scripts/design_log.py append --log <design_log.jsonl> --batch <id> --phase <phase>
            --points <json or file> [--justification '<type> → <target>']
            --design-method '<tool, criterion, seed>' | 'manual: <reason>'
    python3 scripts/design_log.py hook --log <design_log.jsonl> --witness <design_witness.jsonl>
            (--points-key <dotted key into tool_input> | --points <json or file>) [--tool <name>]
            [--require-analysis [--free-batches N] [--runs <dir>] [--comparisons <dir>]]

`append` writes one entry: seq, prev (sha256 of the previous line), written_at
(UTC, taken from the clock, not from the caller), batch, phase, points,
design_method. Every point has a name, its conditions and exactly one
justification (P5): its own `justification` in --points, or the
--justification default for points that give none. A target is one line
with no backtick; a `|` in it or in the design method is written `\\|`; a `;`
is allowed. Entries are never edited or deleted.

`hook` is the integration point before an experiment call. As a Claude Code
PreToolUse hook it reads the hook JSON from stdin; from a CLI wrapper it takes
--points. It admits the call only if every point matches an unused point of
the latest entry, then appends a witness record (time, tool, design_lines,
design_head, points). Each witness point carries the executed conditions as
passed and the `name` of the registered point it was matched to, also when
the tool input is unnamed (witnesses before kit 0.4.1 kept the tool's label,
or null). Exit 0 admit, 2 block (reason on stderr), 1 usage error.

With --require-analysis (off by default) the hook also checks that the run is
sequential: a call that starts a new batch is admitted only if the previous
batch is analysed, i.e. a RUN in --runs lists every experiment of that batch in
its `**Experiments**:` and, when that batch is the second or later, so does a
COMPARISON in --comparisons. The first --free-batches batches (default 1) start
without it. --runs and --comparisons default to `runs/` and `comparisons/` next
to the log. The admitted call's witness record then carries `analysed`:
{batch, runs, comparisons} with the IDs that covered the previous batch. This
is the mechanical form of RUN rule 10 and COMPARISON rule 5: a batch's
justification comes from the latest RUN and COMPARISON.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path

TYPES = ("variance", "information", "boundary")
FIELDS = ("seq", "prev", "written_at", "batch", "phase", "points", "design_method")
RTOL, ATOL = 1e-6, 1e-9


# ── parsing ─────────────────────────────────────────────────────

def parse_time(v):
    """ISO 8601 with an offset (or Z), or epoch seconds, to an aware datetime; None if invalid."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v, dt.timezone.utc) if math.isfinite(v) else None
    if not isinstance(v, str):
        return None
    s = v.strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return dt.datetime.fromtimestamp(float(s), dt.timezone.utc)
    try:
        t = dt.datetime.fromisoformat(re.sub(r"Z$", "+00:00", s))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def norm_points(raw) -> list:
    """Points as [{'name': str|None, 'conditions': {key: value}}].

    Accepts a list of {'name', 'conditions'[, 'justification']} objects, a list
    of bare condition objects, or a mapping label -> conditions (the shape of a
    simulate request) or label -> {'conditions', 'justification'}. A condition
    value is a number, a string, or a list or object of them at any depth; no
    null, no boolean. A point's justification is kept raw under 'justification'
    (None if absent). Raises ValueError on anything else."""
    if isinstance(raw, dict):
        raw = [{**v, "name": k} if isinstance(v, dict) and isinstance(v.get("conditions"), dict)
               else {"name": k, "conditions": v} for k, v in raw.items()]
    if not isinstance(raw, list) or not raw:
        raise ValueError("points must be a non-empty list or a non-empty label -> conditions mapping")
    out = []
    for p in raw:
        just = None
        if isinstance(p, dict) and isinstance(p.get("conditions"), dict):
            name, cond, just = p.get("name"), p["conditions"], p.get("justification")
        elif isinstance(p, dict):
            name, cond = None, p
        else:
            raise ValueError(f"point {p!r} is not an object")
        if not cond:
            raise ValueError("a point has no conditions")
        for k, v in cond.items():
            check_value(str(k), v)
        out.append({"name": None if name is None else str(name), "conditions": dict(cond), "justification": just})
    return out


def check_value(path: str, v) -> None:
    """Raise ValueError unless v is a finite number, a string, or a list or
    object of them at any depth."""
    if isinstance(v, list):
        for i, x in enumerate(v):
            check_value(f"{path}[{i}]", x)
    elif isinstance(v, dict):
        for k, x in v.items():
            check_value(f"{path}.{k}", x)
    elif isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ValueError(f"condition {path}={v!r} is neither a number, a string, nor a list or object of them")
    elif isinstance(v, float) and not math.isfinite(v):
        raise ValueError(f"condition {path}={v!r} is not finite")


def same_value(x, y, rtol=RTOL, atol=ATOL) -> bool:
    """Numbers within tolerance, other scalars equal as stripped strings; lists of
    the same length element by element, objects with the same keys key by key."""
    if isinstance(x, dict) or isinstance(y, dict):
        return isinstance(x, dict) and isinstance(y, dict) and set(x) == set(y) \
            and all(same_value(x[k], y[k], rtol, atol) for k in x)
    if isinstance(x, list) or isinstance(y, list):
        return isinstance(x, list) and isinstance(y, list) and len(x) == len(y) \
            and all(same_value(a, b, rtol, atol) for a, b in zip(x, y))
    if isinstance(x, (int, float)) and isinstance(y, (int, float)) \
            and not isinstance(x, bool) and not isinstance(y, bool):
        return math.isclose(x, y, rel_tol=rtol, abs_tol=atol)
    return str(x).strip() == str(y).strip()


def same_point(a: dict, b: dict, rtol=RTOL, atol=ATOL) -> bool:
    """Same condition keys and same structure; numbers within tolerance element
    by element, strings equal. Key order is ignored, list order is not."""
    return same_value(a, b, rtol, atol)


def norm_text(s: str) -> str:
    """Comparison form of a justification target or design method."""
    s = str(s).replace("`", "").replace("->", "→").replace("\\|", "|")
    return re.sub(r"\s+", " ", s).strip().lower()


def cell_breaker(s: str):
    """What in `s` would break a DATASET table cell it is copied into verbatim, or None."""
    if re.search(r"[\r\n]", s):
        return "a line break"
    if re.search(r"(?<!\\)\|", s):
        return "a `|` (write it `\\|`)"
    return None


def parse_justification(s):
    """'<type> → <target>' or {type, target} to (type, target); None if malformed."""
    if isinstance(s, dict):
        ty, tg = s.get("type"), s.get("target")
        return (ty, tg.strip()) if ty in TYPES and isinstance(tg, str) and tg.strip() else None
    if not isinstance(s, str):
        return None
    m = re.fullmatch(r"\s*(\w+)\s*→\s*(.+?)\s*", str(s).replace("`", "").replace("->", "→"))
    if not m or m.group(1).lower() not in TYPES:
        return None
    return m.group(1).lower(), m.group(2)


# ── the log ─────────────────────────────────────────────────────

def raw_lines(path) -> list:
    """Non-empty lines of the log, without their newline, exactly as stored."""
    text = Path(path).read_bytes().decode("utf-8")
    return [ln for ln in text.split("\n") if ln.strip()]


def line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def prefix_hash(lines: list, n: int) -> str:
    """sha256 of the first n lines, each terminated by a newline."""
    return hashlib.sha256("".join(ln + "\n" for ln in lines[:n]).encode("utf-8")).hexdigest()


def load_log(path):
    """(lines, entries, problems). An entry is the parsed dict with its points
    normalised; problems are (rule, message) for malformed lines (D1) and
    broken append-only evidence (D2)."""
    lines = raw_lines(path)
    entries, probs = [], []
    seen_batch, last_t = {}, None
    for i, ln in enumerate(lines, 1):
        try:
            e = json.loads(ln)
        except json.JSONDecodeError as exc:
            probs.append(("D1", f"line {i}: not JSON ({exc.msg})"))
            entries.append(None)
            continue
        if not isinstance(e, dict):
            probs.append(("D1", f"line {i}: not a JSON object"))
            entries.append(None)
            continue
        missing = [f for f in FIELDS if f not in e]
        if missing:
            probs.append(("D1", f"line {i}: missing field(s) {', '.join(missing)}"))
        if e.get("seq") != i:
            probs.append(("D1", f"line {i}: seq is {e.get('seq')!r}, expected {i} (entries are numbered 1, 2, … in file order)"))
        want = None if i == 1 else line_hash(lines[i - 2])
        if e.get("prev") != want:
            probs.append(("D2", f"line {i}: prev does not match the sha256 of line {i - 1}; "
                                "an earlier line was edited, removed or reordered" if i > 1 else
                                "line 1: prev must be null"))
        t = parse_time(e.get("written_at"))
        if t is None:
            probs.append(("D1", f"line {i}: written_at {e.get('written_at')!r} is not ISO 8601 with an offset"))
        elif last_t is not None and t < last_t:
            probs.append(("D2", f"line {i}: written_at {e['written_at']} is earlier than the line before it"))
        if t is not None:
            last_t = t
        b = str(e.get("batch", "")).strip()
        if not b:
            probs.append(("D1", f"line {i}: batch is empty"))
        elif b in seen_batch:
            probs.append(("D1", f"line {i}: batch {b} already registered on line {seen_batch[b]}; "
                                "a re-planned batch gets a new batch id"))
        else:
            seen_batch[b] = i
        try:
            pts = norm_points(e.get("points"))
        except ValueError as exc:
            probs.append(("D1", f"line {i}: {exc}"))
            pts = []
        names = set()
        for k, q in enumerate(pts, 1):
            nm = (q["name"] or "").strip()
            if not nm:
                probs.append(("D1", f"line {i}: point {k} has no name"))
            elif nm in names:
                probs.append(("D1", f"line {i}: point name {nm} is used twice in the batch"))
            names.add(nm)
            q["just"] = parse_justification(q["justification"])
            if q["just"] is None:
                probs.append(("D1", f"line {i}: point {nm or k} needs exactly one justification {{type, target}} "
                                    f"with type {', '.join(TYPES)} and a target (P5); got {q['justification']!r}"))
        dm = e.get("design_method")
        if not isinstance(dm, str) or not dm.strip():
            probs.append(("D1", f"line {i}: design_method is empty"))
        elif re.match(r"\s*manual\s*:", dm, re.I) and not dm.split(":", 1)[1].strip():
            probs.append(("D1", f"line {i}: design_method `manual:` gives no reason the tool was not used (P5)"))
        entries.append({"seq": i, "batch": b, "phase": e.get("phase"), "time": t, "written_at": e.get("written_at"),
                        "points": pts, "design_method": dm if isinstance(dm, str) else ""})
    return lines, entries, probs


def make_entry(lines: list, batch, phase, points, justification, design_method, written_at=None) -> str:
    """The JSON line that appends one entry after `lines`. `justification` is the
    default for points that carry none: None, one string or a one-item list.
    Raises ValueError on bad input."""
    if isinstance(justification, (list, tuple)):
        if len(justification) > 1:
            raise ValueError("one default justification at most; give per-point justifications inside --points")
        justification = justification[0] if justification else None
    pts = norm_points(points)
    out = []
    for k, q in enumerate(pts, 1):
        name = (q["name"] or "").strip()
        if not name:
            raise ValueError(f"point {k} has no name; give points as label -> conditions or with a `name`")
        if name in (o["name"] for o in out):
            raise ValueError(f"point name {name} is used twice")
        raw = q["justification"] if q["justification"] is not None else justification
        if raw is None:
            raise ValueError(f"point {name} has no justification and no default --justification was given (P5)")
        if isinstance(raw, list):
            raise ValueError(f"point {name}: exactly one justification per point (P5)")
        if isinstance(raw, str) and re.search(r"[\r\n]", raw.strip()):
            raise ValueError(f"point {name}: justification {raw!r} has a line break; a target is one line")
        pj = parse_justification(raw)
        if pj is None:
            raise ValueError(f"point {name}: justification {raw!r} is not `<variance|information|boundary> → <target>`")
        why = "a backtick" if "`" in pj[1] else cell_breaker(pj[1])
        if why:
            raise ValueError(f"point {name}: target {pj[1]!r} has {why}; DATASET section 6 copies it verbatim "
                             "inside backticks in a table cell")
        out.append({"name": name, "conditions": q["conditions"], "justification": {"type": pj[0], "target": pj[1]}})
    if not str(design_method).strip():
        raise ValueError("design method is required")
    why = cell_breaker(str(design_method).strip())
    if why:
        raise ValueError(f"design method {str(design_method).strip()!r} has {why}; DATASET section 6 copies it "
                         "verbatim into a table cell")
    if not str(batch).strip():
        raise ValueError("batch is required")
    e = {"seq": len(lines) + 1, "prev": line_hash(lines[-1]) if lines else None,
         "written_at": written_at or now_iso(), "batch": str(batch).strip(), "phase": phase,
         "points": out, "design_method": str(design_method).strip()}
    return json.dumps(e, ensure_ascii=False, separators=(", ", ": "))


def append_entry(path, *args, **kw) -> str:
    """Append one entry to the log at `path` (created if absent); return the line."""
    p = Path(path)
    lines = raw_lines(p) if p.is_file() else []
    line = make_entry(lines, *args, **kw)
    data = p.read_bytes() if p.is_file() else b""
    with open(p, "ab") as f:
        if data and not data.endswith(b"\n"):
            f.write(b"\n")
        f.write((line + "\n").encode("utf-8"))
    return line


# ── the hook ────────────────────────────────────────────────────

def dig(obj, key: str):
    for part in key.split("."):
        if not isinstance(obj, dict) or part not in obj:
            raise KeyError(key)
        obj = obj[part]
    return obj


def read_json_arg(s: str):
    s = s.strip()
    return json.loads(s if s[:1] in "[{" else Path(s).read_text(encoding="utf-8"))


def witness_names(w: dict, entry) -> list:
    """Names of a witness record's points: as recorded, or (old witnesses) matched to the entry."""
    free = list(entry["points"]) if entry else []
    out = []
    for q in norm_points(w.get("points")):
        k = next((k for k, x in enumerate(free) if same_point(x["conditions"], q["conditions"])), None)
        reg = free.pop(k)["name"] if k is not None else None
        out.append(q["name"] or reg)
    return [n for n in out if n]


def check_analysis(entries, records, n, analysis) -> dict:
    """The previous batch is analysed before the batch of entry n starts; returns the evidence.
    Raises PermissionError naming what to write."""
    from result_gate import load_comparison, load_run, read      # lazy: only with --require-analysis
    started = []
    for w in records:
        if w.get("design_lines") not in started:
            started.append(w.get("design_lines"))
    if n in started or len(started) < analysis["free"] or not started:
        return {}
    k = started[-1]
    entry = entries[k - 1] if isinstance(k, int) and 0 < k <= len(entries) else None
    names = set()
    for w in records:
        if w.get("design_lines") == k:
            names.update(witness_names(w, entry))
    batch = entry["batch"] if entry else f"of design-log line {k}"

    def covering(d, loader):
        out, p = [], Path(d)
        for f in sorted(p.glob("*.md")) if p.is_dir() else []:
            text = read(f)
            doc = loader(f, text) if text is not None else None
            if doc and doc["experiments"] is not None and names <= set(doc["experiments"]):
                out.append(doc["id"] or f.name)
        return out
    runs = covering(analysis["runs"], load_run)
    need_comp = len(started) >= 2
    comps = covering(analysis["comparisons"], load_comparison) if need_comp else []
    missing = ([f"a RUN in {analysis['runs']}"] if not runs else []) + \
              ([f"a COMPARISON in {analysis['comparisons']}"] if need_comp and not comps else [])
    if missing:
        raise PermissionError(
            f"batch {batch} is not analysed yet: write {' and '.join(missing)} whose `**Experiments**:` include "
            f"{', '.join(sorted(names)) or 'its experiments'}, then call again. A batch is run to be analysed; the "
            "next batch is designed from the latest RUN and COMPARISON (RUN rule 10, COMPARISON rule 5). The first "
            f"{analysis['free']} batch(es) start without analysis (--free-batches)")
    return {"batch": entry["batch"] if entry else None, "runs": runs, "comparisons": comps}


def admit(log, witness, points, tool="", analysis=None) -> str:
    """Admit one experiment call or raise PermissionError with the reason.
    On admission append a witness record and return it. `analysis` is None or
    {"runs": dir, "comparisons": dir, "free": N} (--require-analysis)."""
    if not Path(log).is_file():
        raise PermissionError(f"no design log at {log}: append the batch with design_log.py append before the call (P5)")
    lines, entries, probs = load_log(log)
    if probs:
        raise PermissionError("design log is not valid: " + "; ".join(f"[{r}] {m}" for r, m in probs[:5]))
    if not entries:
        raise PermissionError("design log is empty: append the batch before the call (P5)")
    n, open_e = len(lines), entries[-1]
    pts = norm_points(points)
    used, records = [], []
    wp = Path(witness)
    if wp.is_file():
        for ln in raw_lines(wp):
            try:
                w = json.loads(ln)
            except json.JSONDecodeError:
                raise PermissionError(f"witness {witness} has a line that is not JSON; it is written by this hook only")
            records.append(w)
            if w.get("design_lines") == n and w.get("design_head") == prefix_hash(lines, n):
                used += [q["conditions"] for q in norm_points(w.get("points"))]
    free = list(open_e["points"])
    for u in used:
        for k, q in enumerate(free):
            if same_point(q["conditions"], u):
                del free[k]
                break
    matched = []
    for p in pts:
        for k, q in enumerate(free):
            if same_point(q["conditions"], p["conditions"]):
                matched.append(q["name"])
                del free[k]
                break
        else:
            raise PermissionError(
                f"point {json.dumps(p['conditions'], sort_keys=True)} is not an unused point of the latest design-log "
                f"entry (seq {n}, batch {open_e['batch']}); append an entry for it first (P5)")
    evidence = check_analysis(entries, records, n, analysis) if analysis else {}
    rec = {"time": now_iso(), "tool": tool, "design_lines": n, "design_head": prefix_hash(lines, n),
           "points": [{"name": nm, "conditions": p["conditions"]} for nm, p in zip(matched, pts)]}
    if evidence:
        rec["analysed"] = evidence
    line = json.dumps(rec, ensure_ascii=False, separators=(", ", ": "))
    with open(wp, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


# ── CLI ─────────────────────────────────────────────────────────

def opts(argv, multi=("--justification",)):
    o, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if not a.startswith("--") or i + 1 >= len(argv):
            raise ValueError(a)
        if a in multi:
            o.setdefault(a, []).append(argv[i + 1])
        else:
            o[a] = argv[i + 1]
        i += 2
    return o


def main(argv=None, stdin=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("append", "hook"):
        print(__doc__)
        return 1
    cmd = argv.pop(0)
    require = cmd == "hook" and "--require-analysis" in argv
    argv = [a for a in argv if not (cmd == "hook" and a == "--require-analysis")]
    try:
        o = opts(argv)
    except ValueError:
        print(__doc__)
        return 1
    if cmd == "append":
        need = ("--log", "--batch", "--phase", "--points", "--design-method")
        if any(k not in o for k in need) or set(o) - set(need) - {"--justification"}:
            print(__doc__)
            return 1
        try:
            line = append_entry(o["--log"], o["--batch"], o["--phase"], read_json_arg(o["--points"]),
                                o.get("--justification"), o["--design-method"])
        except (ValueError, OSError) as exc:
            print(f"design_log: {exc}", file=sys.stderr)
            return 1
        print(line)
        return 0
    if "--log" not in o or "--witness" not in o or ("--points-key" in o) == ("--points" in o) \
            or set(o) - {"--log", "--witness", "--points-key", "--points", "--tool", "--free-batches", "--runs",
                         "--comparisons"} \
            or (not require and {"--free-batches", "--runs", "--comparisons"} & set(o)) \
            or not re.fullmatch(r"\d+", o.get("--free-batches", "1")):
        print(__doc__)
        return 1
    analysis = None
    if require:
        base = Path(o["--log"]).parent
        analysis = {"runs": o.get("--runs", str(base / "runs")),
                    "comparisons": o.get("--comparisons", str(base / "comparisons")),
                    "free": int(o.get("--free-batches", "1"))}
    try:
        if "--points" in o:
            points, tool = read_json_arg(o["--points"]), o.get("--tool", "")
        else:
            payload = json.load(stdin or sys.stdin)
            points, tool = dig(payload.get("tool_input") or {}, o["--points-key"]), payload.get("tool_name", "")
        admit(o["--log"], o["--witness"], points, o.get("--tool", tool), analysis)
    except (PermissionError, KeyError, ValueError, OSError) as exc:
        msg = f"cannot read the conditions at {exc}" if isinstance(exc, KeyError) else str(exc)
        print(f"design_log hook: call blocked: {msg}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
