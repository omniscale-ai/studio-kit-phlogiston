#!/usr/bin/env python3
"""Gate for P5: every executed experiment was pre-registered. Stdlib only.
Exit 0 PASS, 1 FAIL, 2 usage error or unreadable --source / --dataset.

    python3 scripts/design_gate.py <design_log.jsonl> --source <acquisitions>
            [--dataset <DATASET.md>] [--require-commit] [--rtol R] [--atol A]

<design_log.jsonl> is written by the agent through `design_log.py append`.
--source is written by something other than the agent: the oracle or
simulator log converted to the acquisitions format, or the witness file of
`design_log.py hook`. JSONL, one call per line: `time` plus `points` (list or
label -> conditions) or `conditions`, optionally `design_lines` and
`design_head`; or CSV, one experiment per row: `time`, optional `call` and
`name`, every other column a condition. Checks D1-D5 are those of the
"Design gate" table in artifacts/DATASET/rules.md. One line per violation
`[Dk] message`, `note:` lines for registered points never run, then PASS or
FAIL - n violation(s).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_log import (ATOL, RTOL, load_log, norm_points, norm_text, parse_justification,  # noqa: E402
                        parse_time, prefix_hash, same_point)


class SourceError(Exception):
    """The acquisitions source or the DATASET cannot be read: no verdict."""


def num(v: str):
    v = (v or "").strip()
    return float(v) if re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", v) else v


def load_source(path) -> list:
    """Calls as dicts {where, time, points, lines, head}, in time order."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(f"cannot read --source {path}: {exc}")
    calls = []
    if p.suffix.lower() == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
        if not rows or "time" not in rows[0]:
            raise SourceError(f"--source {path}: CSV needs a header with a `time` column and at least one row")
        groups = {}
        for i, r in enumerate(rows, 2):
            key = r.get("call") or f"row{i}"
            cond = {k: num(v) for k, v in r.items() if k not in ("time", "call", "name") and k is not None}
            g = groups.setdefault(key, {"where": f"{p.name} row {i}", "time": r["time"], "points": [],
                                        "lines": None, "head": None})
            g["points"].append({"name": r.get("name"), "conditions": cond})
        raw = list(groups.values())
    else:
        raw = []
        for i, ln in enumerate(text.splitlines(), 1):
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except json.JSONDecodeError as exc:
                raise SourceError(f"--source {path} line {i}: not JSON ({exc.msg})")
            if not isinstance(d, dict):
                raise SourceError(f"--source {path} line {i}: not a JSON object")
            raw.append({"where": f"{p.name} line {i}", "time": d.get("time"),
                        "points": d.get("points", d.get("conditions")),
                        "lines": d.get("design_lines"), "head": d.get("design_head")})
    for c in raw:
        t = parse_time(c["time"])
        if t is None:
            raise SourceError(f"{c['where']}: time {c['time']!r} is not ISO 8601 with an offset or epoch seconds")
        try:
            pts = norm_points(c["points"])
        except ValueError as exc:
            raise SourceError(f"{c['where']}: {exc}")
        calls.append({**c, "time": t, "points": pts})
    calls.sort(key=lambda c: c["time"])
    return calls


def acquisition_rows(path) -> list:
    """(batch, justification cell, design method cell) per row of the first table in section 6."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(f"cannot read --dataset {path}: {exc}")
    m = re.search(r"^##\s+6\.\s*Acquisition\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        raise SourceError(f"--dataset {path}: no `## 6. Acquisition` section")
    rows = [ln.strip() for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    if len(rows) < 2:
        raise SourceError(f"--dataset {path}: section 6 has no table")
    cells = lambda ln: [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]  # noqa: E731
    head = [c.lower() for c in cells(rows[0])]

    def col(prefix):
        for k, h in enumerate(head):
            if h.startswith(prefix):
                return k
        raise SourceError(f"--dataset {path}: section 6 table has no `{prefix}` column")
    b, j, d = col("batch"), col("justification"), col("design method")
    out = []
    for ln in rows[1:]:
        c = cells(ln)
        if all(re.fullmatch(r":?-+:?", x) for x in c if x):
            continue
        c += [""] * (len(head) - len(c))
        out.append((c[b].replace("`", "").strip(), c[j], c[d]))
    return out


NAMED = re.compile(r"^\s*(?P<names>[^:→]+?)\s*:\s*(?P<pair>\w+\s*→.*)$")


def check_cell(b, e, cell, executed, bad):
    """D5 for one Justification cell: one shared `type → target` for every experiment
    that ran, or `<names>: type → target` parts covering each of them."""
    key = lambda pj: (pj[0], norm_text(pj[1]))  # noqa: E731
    show = lambda pj: f"{pj[0]} → {pj[1]}"  # noqa: E731
    logged = {q["name"]: q["just"] for q in e["points"] if q.get("just")}
    parts = [x.replace("`", "").replace("->", "→") for x in re.split(r";|<br\s*/?>", cell) if x.strip()]
    if not parts:
        bad("D5", f"DATASET batch {b}: Justification is empty; copy it from the design log line {e['seq']}")
        return
    if len(parts) == 1 and not NAMED.match(parts[0]):
        pj = parse_justification(parts[0])
        if pj is None:
            bad("D5", f"DATASET batch {b}: justification `{parts[0].strip()}` is not `<variance|information|boundary> → <target>`")
            return
        for n in executed:
            if n in logged and key(logged[n]) != key(pj):
                bad("D5", f"DATASET batch {b}: one justification `{show(pj)}` for the whole batch, but the design log "
                          f"line {e['seq']} justifies {n} as `{show(logged[n])}`; list them as `<names>: type → target`")
        return
    cell_map = {}
    for x in parts:
        m = NAMED.match(x)
        pj = parse_justification(m.group("pair")) if m else None
        if pj is None:
            bad("D5", f"DATASET batch {b}: `{x.strip()}` is not `<names>: <variance|information|boundary> → <target>`")
            continue
        for n in (y.strip() for y in m.group("names").split(",") if y.strip()):
            if n in cell_map:
                bad("D5", f"DATASET batch {b}: experiment {n} has two justifications")
            cell_map[n] = pj
    for n, pj in cell_map.items():
        if n not in logged:
            bad("D5", f"DATASET batch {b}: experiment {n} is not a point of the design log line {e['seq']}")
        elif key(pj) != key(logged[n]):
            bad("D5", f"DATASET batch {b}: experiment {n} is justified as `{show(pj)}`, the design log line {e['seq']} "
                      f"says `{show(logged[n])}`; copy it, do not reconstruct it")
    for n in executed:
        if n not in cell_map:
            bad("D5", f"DATASET batch {b}: experiment {n} ran and has no justification in the cell")


def check(log, source, dataset=None, require_commit=False, rtol=RTOL, atol=ATOL):
    """(violations, notes)."""
    fails, notes = [], []
    calls = load_source(source)
    rows = acquisition_rows(dataset) if dataset else None

    def bad(rule, msg):
        fails.append(f"[{rule}] {msg}")

    if not Path(log).is_file():
        n_exp = sum(len(c["points"]) for c in calls)
        bad("D1", f"design log {log} does not exist; {n_exp} executed experiment(s) in {len(calls)} call(s) "
                  "have no pre-registration (P5)")
        if rows:
            bad("D5", f"DATASET section 6 has {len(rows)} batch row(s) and there is no design log they were copied from")
        return fails, notes
    try:
        lines, entries, probs = load_log(log)
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(f"cannot read the design log {log}: {exc}")
    for r, m in probs:
        bad(r, m)
    good = [e for e in entries if e is not None]
    if not good and calls:
        bad("D1", f"design log {log} has no entry; {len(calls)} call(s) were executed")
    free = {e["seq"]: list(e["points"]) for e in good}
    ran = {e["seq"]: 0 for e in good}
    ran_names = {e["seq"]: [] for e in good}
    fmt = lambda c: json.dumps(c, sort_keys=True)  # noqa: E731

    for c in calls:
        when = c["time"].isoformat()
        vis = None
        if c["head"] is not None or c["lines"] is not None:
            n = c["lines"]
            if not isinstance(n, int) or not 0 < n <= len(lines) or c["head"] != prefix_hash(lines, n):
                bad("D2", f"{c['where']} (call at {when}): the design log no longer starts with the {n!r} line(s) "
                          "recorded at call time; it was rewritten after the call")
            else:
                vis = n
                for e in good:
                    if e["seq"] > n and e["time"] is not None and e["time"] < c["time"]:
                        bad("D2", f"line {e['seq']} (batch {e['batch']}): written_at {e['written_at']} is before "
                                  f"the call at {when}, but the log had only {n} line(s) then; written_at was backdated")
        elif require_commit:
            bad("D3", f"{c['where']} (call at {when}): no design_head / design_lines recorded; with --require-commit "
                      "every call carries the log commitment from design_log.py hook")
        if vis is None:
            vis = max((e["seq"] for e in good if e["time"] is not None and e["time"] < c["time"]), default=0)
        if vis == 0:
            later = next((e for e in good if any(same_point(q["conditions"], p["conditions"], rtol, atol)
                                                 for q in e["points"] for p in c["points"])), None)
            where = (f"; its points were registered later, line {later['seq']} (batch {later['batch']}) "
                     f"written_at {later['written_at']}" if later else "")
            bad("D3", f"{c['where']}: call at {when} ran {len(c['points'])} experiment(s) before any design-log "
                      f"entry was written (P5: justified before it runs){where}")
            continue
        open_e = next((e for e in good if e["seq"] == vis), None)
        if open_e is None:
            bad("D1", f"{c['where']}: the open entry, line {vis}, is malformed")
            continue
        for p in c["points"]:
            cond, label = p["conditions"], f" ({p['name']})" if p["name"] else ""
            k = next((k for k, q in enumerate(free[vis]) if same_point(q["conditions"], cond, rtol, atol)), None)
            if k is not None:
                ran_names[vis].append(free[vis][k]["name"])
                del free[vis][k]
                ran[vis] += 1
                continue
            later = next((e for e in good if e["seq"] > vis
                          and any(same_point(q["conditions"], cond, rtol, atol) for q in e["points"])), None)
            older = next((e for e in reversed(good) if e["seq"] < vis
                          and any(same_point(q["conditions"], cond, rtol, atol) for q in e["points"])), None)
            if later:
                bad("D3", f"{c['where']}: experiment{label} {fmt(cond)} ran at {when} but was registered later, "
                          f"line {later['seq']} (batch {later['batch']}) written_at {later['written_at']}")
            elif older:
                bad("D4", f"{c['where']}: experiment{label} {fmt(cond)} matches batch {older['batch']}, which was "
                          f"closed by line {vis} (batch {open_e['batch']}) before the call; register it again")
            elif any(same_point(q["conditions"], cond, rtol, atol) for q in open_e["points"]):
                bad("D4", f"{c['where']}: experiment{label} {fmt(cond)} ran more times than batch "
                          f"{open_e['batch']} registered it")
            else:
                near = open_e["points"][0]["conditions"] if open_e["points"] else {}
                bad("D4", f"{c['where']}: experiment{label} {fmt(cond)} matches no point of the open entry, "
                          f"line {vis} (batch {open_e['batch']}), e.g. {fmt(near)} (rtol {rtol:g}, atol {atol:g})")

    for e in good:
        if free.get(e["seq"]):
            notes.append(f"note: batch {e['batch']} (line {e['seq']}): {len(free[e['seq']])} registered point(s) "
                         "never ran; say why in Known Defects")

    if rows is not None:
        by_batch = {e["batch"]: e for e in good}
        seqs = []
        for b, jcell, dcell in rows:
            e = by_batch.get(b)
            if e is None:
                bad("D5", f"DATASET batch {b}: no design-log entry with batch {b}")
                continue
            seqs.append(e["seq"])
            check_cell(b, e, jcell, ran_names[e["seq"]], bad)
            if norm_text(dcell) != norm_text(e["design_method"]):
                bad("D5", f"DATASET batch {b}: design method `{dcell}` differs from the design log line {e['seq']} "
                          f"`{e['design_method']}`")
        if seqs != sorted(seqs):
            bad("D5", "DATASET section 6 rows are not in design-log order")
        listed = {b for b, _, _ in rows}
        for e in good:
            if ran[e["seq"]] and e["batch"] not in listed:
                bad("D5", f"batch {e['batch']} (line {e['seq']}) ran {ran[e['seq']]} experiment(s) and has no "
                          "DATASET section 6 row")
    return fails, notes


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    o, files, i = {}, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--require-commit":
            o[a] = True
        elif a in ("--source", "--dataset", "--rtol", "--atol"):
            if i + 1 >= len(argv):
                print(__doc__)
                return 2
            o[a] = argv[i + 1]
            i += 1
        elif a.startswith("-"):
            print(__doc__)
            return 2
        else:
            files.append(a)
        i += 1
    if len(files) != 1 or "--source" not in o or not Path(o["--source"]).is_file() \
            or ("--dataset" in o and not Path(o["--dataset"]).is_file()):
        print(__doc__)
        return 2
    try:
        rtol, atol = float(o.get("--rtol", RTOL)), float(o.get("--atol", ATOL))
        fails, notes = check(files[0], o["--source"], o.get("--dataset"), bool(o.get("--require-commit")), rtol, atol)
    except ValueError:
        print(__doc__)
        return 2
    except SourceError as exc:
        print(f"design_gate: {exc}", file=sys.stderr)
        return 2
    for f in fails + notes:
        print(f)
    print("PASS" if not fails else f"FAIL — {len(fails)} violation(s)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
