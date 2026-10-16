#!/usr/bin/env python3
"""Gate for a final result: the submitted candidate was selected by a COMPARISON
of structurally different RUNs on the final snapshot, and the stopping rule
holds. Stdlib only.

    python3 scripts/result_gate.py --plan <PLAN.md> --dataset <DATASET.md>
            --runs <runs dir> --comparisons <comparisons dir> --submission <file>
            [--source <acquisitions>] [--budget-left N]
    python3 scripts/result_gate.py hook --witness <result_witness.jsonl> <the same options>

Gate mode prints one line per violation `[Rk] message`, `note:` lines, then
PASS or FAIL - n violation(s). Exit 0 PASS, 1 FAIL, 2 usage error or an
unreadable --source / --submission.

Checks R1-R6 are those of the "Result gate" table in
artifacts/COMPARISON/rules.md:

  R1  the final COMPARISON (on the final snapshot, not superseded) exists:
      its section 1 `**Dataset**:` is the DATASET's ID and its
      `**Experiments**:` are exactly the experiments acquired, from --source
      if given, else from DATASET section 6; a COMPARISON on an older
      snapshot does not count.
  R2  it lists at least two candidate RUNs, every listed RUN exists and is on
      the same snapshot, every RUN on that snapshot is listed, and at least two
      have different `**Structure**:` (RUN section 3) and different Candidate
      Specs: a parameter variant is not an alternative.
  R3  section 3 columns are the PLAN's criterion IDs in the PLAN's order; each
      RUN's Verdict has exactly those rows; each COMPARISON row equals its
      RUN's Verdict results (pass / fail / not evaluated; p, f, n/e accepted).
  R4  section 5 `**Selected**:` names a listed RUN that passes every
      mechanical row, has no `not evaluated` row and is dominated by no
      candidate, and the sha256 of --submission equals that RUN's
      `**Candidate sha256**:` (RUN section 3).
  R5  section 6 has a Status column with `open`, `closed by batch <id>`
      (a DATASET batch whose Justification has an `information →` target) or
      `unresolvable: <reason>`; every candidate the selected one does not
      dominate is in a pair with it; and no pair is `open` while
      --budget-left > 0 (or when --budget-left is not given: the gate fails
      closed). A reason about using fewer experiments or saving budget is not
      a reason.
  R6  every RUN and COMPARISON file passes the structural checks of `cfs
      validate`, replicated from the kit's constraints.toml: one H1, an
      `**ID**:` of its kind, unique across files, every required numbered
      section present once, in order, numbered 1, 2, ... consecutively.

Without a COMPARISON on the final snapshot, R2-R5 are not evaluated (a `note:`
says so); the missing COMPARISON is already an R1 violation. Missing PLAN,
DATASET, RUN or COMPARISON files are violations, never usage errors.

Hook mode is meant for a trusted party (oracle or harness) right before it
accepts a final result; run it from the repository's copy of the kit, never
the agent's. It runs the same checks, appends one JSON line to --witness and
exits 0 to accept, 2 to refuse (the report goes to stderr), 1 on a usage
error (nothing is written). The witness line:

  {"time": ISO 8601 UTC, "gate": "result_gate", "version": "0.4.0",
   "gate_sha256": sha256 of this script, "verdict": "PASS" | "FAIL" | "ERROR",
   "violations": ["[Rk] ...", ...], "notes": [...], "submission": path,
   "submission_sha256": hex | null, "comparison": ID | null,
   "selected": RUN ID | null, "budget_left": int | null,
   "source": path | null, "source_sha256": hex | null}

ERROR means the source or the submission could not be read; it refuses.
--source is in the acquisitions format of design_gate.py (JSONL calls with
named `points`, or CSV with a `name` column): a record the agent does not
write. --budget-left is the number of experiment batches (calls) the run may
still make.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from design_gate import SourceError, load_source  # noqa: E402

VERSION = "0.4.0"
CONSTRAINTS = HERE.parent / "constraints.toml"
SHA = re.compile(r"[0-9a-f]{64}")
RESULTS = {"pass": "pass", "p": "pass", "fail": "fail", "f": "fail",
           "not evaluated": "not evaluated", "n/e": "not evaluated", "ne": "not evaluated"}
NOT_A_REASON = re.compile(r"\bfewer\s+(experiments|batches|calls|runs)\b|\bsav(e|es|ing)\s+(the\s+)?"
                          r"(remaining\s+)?(budget|experiments|batches|calls)\b|\bbudget\s+efficien", re.I)


# ── markdown ────────────────────────────────────────────────────

def strip_fences(text: str) -> str:
    """The text with fenced code blocks blanked, line count kept."""
    out, fence = [], False
    for ln in text.split("\n"):
        if re.match(r"\s*(```|~~~)", ln):
            fence = not fence
            out.append("")
            continue
        out.append("" if fence else ln)
    return "\n".join(out)


def sections(text: str) -> dict:
    """{title in lower case: body} for `## N. Title` headings, first occurrence;
    looked up by title, so a missing or renumbered section does not shift the others."""
    out = {}
    ms = list(re.finditer(r"^##\s+\d+\.\s*(.+?)\s*$", text, re.M))
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else len(text)
        nxt = re.search(r"^##\s", text[m.end():end], re.M)
        body = text[m.end():m.end() + nxt.start()] if nxt else text[m.end():end]
        out.setdefault(m.group(1).strip().lower(), body)
    return out


def field(body: str, name: str):
    """Value of the first `**Name**: value` line in body (backticks kept), or None."""
    m = re.search(rf"^\s*(?:[-*]\s+)?\*\*{re.escape(name)}\*\*\s*:\s*(.*?)\s*$", body, re.M | re.I)
    return m.group(1) if m else None


def cells(line: str) -> list:
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def tables(body: str) -> list:
    """Every table in body as a list of rows of cells, separator rows dropped."""
    out, cur = [], []
    for ln in body.split("\n") + [""]:
        if ln.strip().startswith("|"):
            c = cells(ln)
            if not all(re.fullmatch(r":?-+:?", x) for x in c if x) or not any(c):
                cur.append(c)
        elif cur:
            out.append(cur)
            cur = []
    return out


def plain(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("`", "").replace("*", "")).strip()


def ids_in(s: str, kind: str) -> list:
    return [t for t in re.findall(r"cpt-[A-Za-z0-9_-]+", s or "") if f"-{kind}-" in t]


def doc_id(text: str, kind: str):
    v = field(text, "ID")
    got = ids_in(v or "", kind)
    return got[0] if got else None


def names(value: str) -> list:
    """Experiment names from `e1, e2, e5–e9` (en dash or `..` for a numeric range)."""
    out = []
    for part in re.split(r"[,;]", (value or "").replace("`", "")):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\D*?)(\d+)\s*(?:–|\.\.)\s*(\D*?)(\d+)", part)
        if m and m.group(3) in ("", m.group(1)) and int(m.group(2)) <= int(m.group(4)):
            w = len(m.group(2)) if m.group(2).startswith("0") else 0
            out += [f"{m.group(1)}{str(i).zfill(w)}" for i in range(int(m.group(2)), int(m.group(4)) + 1)]
        else:
            out.append(part)
    return out


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def result(cell: str):
    """pass / fail / not evaluated, or None if the cell is none of them."""
    return RESULTS.get(plain(cell).lower())


# ── R6: structure, replicated from constraints.toml ─────────────

def load_constraints(path=CONSTRAINTS) -> dict:
    """{KIND: [heading dict, ...]} from the [[artifacts.KIND.headings]] blocks."""
    out, cur = {}, None
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        s = ln.split("#", 1)[0].strip() if not re.search(r'=\s*"', ln) else ln.strip()
        m = re.fullmatch(r"\[\[artifacts\.(\w+)\.headings\]\]", s)
        if m:
            cur = {}
            out.setdefault(m.group(1), []).append(cur)
            continue
        if s.startswith("["):
            cur = None
            continue
        m = re.fullmatch(r'(\w+)\s*=\s*(".*?"|true|false|\d+)\s*(#.*)?', s)
        if cur is not None and m:
            v = m.group(2)
            cur[m.group(1)] = v[1:-1] if v.startswith('"') else v == "true" if v in ("true", "false") else int(v)
    return out


def check_structure(kind: str, path: Path, text: str, cons: list, bad) -> None:
    lab = path.name
    heads = [(len(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(#{1,6})\s+(.+?)\s*#*\s*$", text, re.M)]
    if sum(1 for lv, _ in heads if lv == 1) != 1:
        bad("R6", f"{lab}: needs exactly one H1 title, found {sum(1 for lv, _ in heads if lv == 1)}")
    if doc_id(text, kind.lower()) is None:
        bad("R6", f"{lab}: no `**ID**: `cpt-<system>-{kind.lower()}-<slug>`` line")
    h2 = [t for lv, t in heads if lv == 2]
    nums = [int(m.group(1)) for t in h2 for m in [re.match(r"(\d+)\.\s", t)] if m]
    if nums != list(range(1, len(nums) + 1)):
        bad("R6", f"{lab}: numbered sections are {nums}, expected 1, 2, ... in order")
    order = []
    for c in cons:
        if c.get("level") != 2 or "pattern" not in c:
            continue
        hits = [k for k, t in enumerate(h2) if re.sub(r"^\d+\.\s*", "", t).strip().lower() == c["pattern"].lower()]
        if not hits:
            if c.get("required"):
                bad("R6", f"{lab}: required section `{c['pattern']}` is missing")
            continue
        if len(hits) > 1 and not c.get("multiple"):
            bad("R6", f"{lab}: section `{c['pattern']}` appears {len(hits)} times")
        if c.get("numbered") and not re.match(r"\d+\.\s", h2[hits[0]]):
            bad("R6", f"{lab}: section `{c['pattern']}` is not numbered")
        order.append((hits[0], c["pattern"]))
    if [p for _, p in order] != [p for _, p in sorted(order)]:
        bad("R6", f"{lab}: sections are out of the template order {', '.join(p for _, p in order)}")


# ── artifacts ───────────────────────────────────────────────────

def read(path):
    try:
        return strip_fences(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def snapshot(body: str):
    """(dataset ID or None, Counter of experiments or None) from a section 1 body."""
    ds = field(body, "Dataset")
    ex = field(body, "Experiments")
    return (ids_in(ds, "dataset") or [None])[0] if ds is not None else None, \
        Counter(names(ex)) if ex is not None else None


def load_plan(path, bad) -> list:
    text = read(path) if path else None
    if text is None:
        bad("R3", f"PLAN {path} not found or unreadable: the criteria the vectors are copied against are unknown")
        return []
    crit = []
    for m in re.finditer(r"^\s*\*\*ID\*\*\s*:\s*(.+)$", text, re.M):
        for c in ids_in(m.group(1), "criterion"):
            if c not in crit:
                crit.append(c)
    if not crit:
        bad("R3", f"PLAN {path}: no `**ID**: `cpt-<system>-criterion-<slug>`` line")
    return crit


def load_dataset(path, bad):
    """{'id', 'rows': [{'batch', 'experiments', 'justification'}]} or None."""
    text = read(path) if path else None
    if text is None:
        bad("R1", f"DATASET {path} not found or unreadable: the final snapshot cannot be named")
        return None
    ds = {"id": doc_id(text, "dataset"), "rows": []}
    if ds["id"] is None:
        bad("R1", f"DATASET {path}: no `**ID**: `cpt-<system>-dataset-<slug>`` line")
    tabs = tables(sections(text).get("acquisition", ""))
    if tabs:
        head = [plain(h).lower() for h in tabs[0][0]]
        col = lambda p: next((k for k, h in enumerate(head) if h.startswith(p)), None)  # noqa: E731
        b, e, j = col("batch"), col("experiments"), col("justification")
        for r in tabs[0][1:]:
            r = r + [""] * (len(head) - len(r))
            ds["rows"].append({"batch": plain(r[b]) if b is not None else "",
                               "experiments": names(r[e]) if e is not None else [],
                               "justification": r[j] if j is not None else ""})
    return ds


def load_run(path: Path, text: str) -> dict:
    sec = sections(text)
    unit = sec.get("unit", "")
    spec = sec.get("candidate spec", "")
    run = {"path": path, "id": doc_id(text, "run")}
    run["dataset"], run["experiments"] = snapshot(unit)
    run["structure"] = plain(field(spec, "Structure") or "") or None
    sha = plain(field(spec, "Candidate sha256") or "").lower()
    run["sha"] = sha if sha else None
    run["spec"] = re.sub(r"\s+", " ", re.sub(r"^\s*(?:[-*]\s+)?\*\*(Structure|Candidate file|Candidate sha256)\*\*.*$",
                                             "", spec, flags=re.M | re.I)).strip()
    run["verdict"] = None
    tabs = tables(sec.get("verdict", ""))
    if tabs:
        head = [plain(h).lower() for h in tabs[0][0]]
        c = next((k for k, h in enumerate(head) if h.startswith("criterion")), None)
        r = next((k for k, h in enumerate(head) if h == "result"), None)
        mb = next((k for k, h in enumerate(head) if h.startswith("measured by")), None)
        if c is not None and r is not None:
            run["verdict"] = []
            for row in tabs[0][1:]:
                row = row + [""] * (len(head) - len(row))
                crit = (ids_in(row[c], "criterion") or [plain(row[c])])[0]
                mech = mb is None or plain(row[mb]).lower().startswith("mechanical")
                run["verdict"].append((crit, row[r], mech))
    return run


def load_comparison(path: Path, text: str) -> dict:
    sec = sections(text)
    comp = {"path": path, "id": doc_id(text, "comparison")}
    s1 = sec.get("snapshot", "")
    comp["dataset"], comp["experiments"] = snapshot(s1)
    comp["supersedes"] = ids_in(field(s1, "Supersedes") or "", "comparison")
    cands = []
    t2 = tables(sec.get("candidates", ""))
    for row in (t2[0][1:] if t2 else []):
        for i in ids_in(row[0], "run")[:1]:
            if i not in cands:
                cands.append(i)
    comp["candidates"] = cands
    t3 = tables(sec.get("criterion vectors", ""))
    comp["columns"] = [(ids_in(h, "criterion") or [plain(h)])[0] for h in t3[0][0][1:]] if t3 else None
    comp["rows"] = [((ids_in(r[0], "run") or [plain(r[0])])[0], r[1:]) for r in t3[0][1:]] if t3 else []
    sel = field(sec.get("selection", ""), "Selected")
    comp["selected"] = None if sel is None else (ids_in(sel, "run") or [plain(sel).lower()])[0]
    t6 = tables(sec.get("open pairs", ""))
    comp["pairs_head"] = [plain(h).lower() for h in t6[0][0]] if t6 else None
    comp["pairs"] = t6[0][1:] if t6 else []
    return comp


def load_dir(d, kind, cons, bad):
    docs, p = [], Path(d) if d else None
    if p is None or not p.is_dir():
        return docs
    for f in sorted(p.glob("*.md")):
        text = read(f)
        if text is None:
            bad("R6", f"{f.name}: unreadable")
            continue
        check_structure(kind, f, text, cons, bad)
        docs.append((load_run if kind == "RUN" else load_comparison)(f, text))
    seen = {}
    for doc in docs:
        if doc["id"] and doc["id"] in seen:
            bad("R6", f"{doc['path'].name}: ID {doc['id']} is also the ID of {seen[doc['id']]}")
        seen.setdefault(doc["id"], doc["path"].name)
    return docs


# ── the checks ──────────────────────────────────────────────────

def diff_text(want: Counter, got: Counter) -> str:
    miss, extra = list((want - got).elements()), list((got - want).elements())
    show = lambda xs: ", ".join(xs[:5]) + (f" (+{len(xs) - 5} more)" if len(xs) > 5 else "")  # noqa: E731
    parts = ([f"misses {show(miss)}"] if miss else []) + ([f"lists {show(extra)}, never acquired"] if extra else [])
    return "; ".join(parts)


def dominates(a: list, b: list) -> bool:
    """a wins or ties every criterion (pass > fail) and wins at least one."""
    return all(x == "pass" or y == "fail" for x, y in zip(a, b)) and any(x == "pass" and y == "fail" for x, y in zip(a, b))


def check(plan, dataset, runs_dir, comps_dir, submission, source=None, budget_left=None):
    """(violations, notes, info). Raises SourceError if --source or --submission
    cannot be read."""
    fails, notes = [], []
    info = {"comparison": None, "selected": None, "submission_sha256": None}

    def bad(rule, msg):
        fails.append(f"[{rule}] {msg}")

    try:
        info["submission_sha256"] = sub_sha = sha256_file(submission)
    except OSError as exc:
        raise SourceError(f"cannot read --submission {submission}: {exc}")
    cons = load_constraints()
    crit = load_plan(plan, bad)
    ds = load_dataset(dataset, bad)
    if source:
        calls = load_source(source)
        acquired = [p["name"] for c in calls for p in c["points"]]
        if any(not n for n in acquired):
            raise SourceError(f"--source {source}: {sum(1 for n in acquired if not n)} experiment(s) have no name; "
                              "the snapshot is checked by experiment name")
        acquired = Counter(str(n).strip() for n in acquired)
    else:
        acquired = Counter(n for r in (ds["rows"] if ds else []) for n in r["experiments"])
    runs = load_dir(runs_dir, "RUN", cons.get("RUN", []), bad)
    comps = load_dir(comps_dir, "COMPARISON", cons.get("COMPARISON", []), bad)
    ds_id = ds["id"] if ds else None

    # R1 — the final COMPARISON
    where = f"--source {Path(source).name}" if source else "DATASET section 6"
    if not acquired:
        bad("R1", f"no experiment acquired according to {where}; there is no snapshot to compare candidates on")
    if not comps:
        bad("R1", f"no COMPARISON in {comps_dir}: a final result is selected by a COMPARISON of candidate RUNs "
                  "on the final snapshot")
    on_final = []
    for c in comps:
        if c["dataset"] is None or c["experiments"] is None:
            bad("R1", f"{c['path'].name}: section 1 needs `**Dataset**: `<DATASET ID>`` and "
                      "`**Experiments**: <names>` lines")
        elif (ds_id is None or c["dataset"] == ds_id) and c["experiments"] == acquired and acquired:
            on_final.append(c)
    gone = {s for c in on_final for s in c["supersedes"]}
    on_final = [c for c in on_final if c["id"] not in gone]
    if comps and not on_final:
        best = max((c for c in comps if c["experiments"] is not None),
                   key=lambda c: sum((c["experiments"] & acquired).values()), default=None)
        if best is not None:
            why = diff_text(acquired, best["experiments"])
            if ds_id and best["dataset"] != ds_id:
                why = f"names DATASET {best['dataset']}, not {ds_id}" + (f"; {why}" if why else "")
            bad("R1", f"no COMPARISON is on the final snapshot ({sum(acquired.values())} experiments in {where}); "
                      f"the closest, {best['path'].name}, {why}. A COMPARISON on an older snapshot does not count")
    if len(on_final) > 1:
        bad("R1", f"{len(on_final)} COMPARISONs on the final snapshot ({', '.join(c['path'].name for c in on_final)}); "
                  "the newest names the others in `**Supersedes**:`")
    if len(on_final) != 1:
        notes.append("note: R2-R5 not evaluated: no single COMPARISON on the final snapshot")
        return fails, notes, info
    comp = on_final[0]
    info["comparison"] = comp["id"]
    cn = comp["path"].name
    by_id = {r["id"]: r for r in runs if r["id"]}

    # R2 — real alternatives
    listed = []
    for rid in comp["candidates"]:
        r = by_id.get(rid)
        if r is None:
            bad("R2", f"{cn}: candidate {rid} has no RUN file in {runs_dir}")
        elif r["dataset"] is None or r["experiments"] is None:
            bad("R2", f"{r['path'].name}: section 1 needs `**Dataset**:` and `**Experiments**:` lines")
        elif r["dataset"] != comp["dataset"] or r["experiments"] != comp["experiments"]:
            bad("R2", f"{cn}: candidate {rid} is not on this snapshot "
                      f"({diff_text(comp['experiments'], r['experiments']) or 'other DATASET'}); "
                      "candidates on different snapshots are not comparable")
        else:
            listed.append(r)
    for r in runs:
        if r["id"] and r["id"] not in comp["candidates"] and r["dataset"] == comp["dataset"] \
                and r["experiments"] == comp["experiments"]:
            bad("R2", f"{cn}: RUN {r['id']} is on this snapshot and is not listed in section 2; "
                      "every candidate run on the snapshot is compared")
    if len(comp["candidates"]) < 2:
        bad("R2", f"{cn}: {len(comp['candidates'])} candidate(s) in section 2; a selection needs at least two, "
                  "of different structure")
    families = {}
    for r in listed:
        if r["structure"] is None:
            bad("R2", f"{r['path'].name}: section 3 has no `**Structure**:` line naming the candidate's "
                      "structural family")
            continue
        fam = r["structure"].lower()
        twin = next((f for f, rs in families.items() if f != fam and any(x["spec"] == r["spec"] for x in rs)), None)
        if twin is not None:
            other = next(x for x in families[twin] if x["spec"] == r["spec"])
            bad("R2", f"{r['id']} and {other['id']} declare different structures but have the same Candidate Spec")
            fam = twin
        families.setdefault(fam, []).append(r)
    if len(listed) >= 2 and len(families) == 1:
        bad("R2", f"{cn}: all {len(listed)} candidates have the structure `{next(iter(families))}`; at least two "
                  "structurally different candidates are needed (a parameter variant is not an alternative)")

    # R3 — vectors copied from the RUNs
    vectors = {}
    if crit and comp["columns"] is None:
        bad("R3", f"{cn}: section 3 has no criterion-vector table")
    elif crit and comp["columns"] != crit:
        bad("R3", f"{cn}: section 3 columns are {', '.join(comp['columns']) or 'none'}; the PLAN's criteria in "
                  f"order are {', '.join(crit)}")
    for r in listed:
        if r["verdict"] is None:
            bad("R3", f"{r['path'].name}: section 9 has no Verdict table with `Criterion ID` and `Result` columns")
            continue
        got = [c for c, _, _ in r["verdict"]]
        if crit and got != crit:
            bad("R3", f"{r['path'].name}: Verdict rows are {', '.join(got) or 'none'}; the PLAN's criteria in order "
                      f"are {', '.join(crit)} (RUN rule 7)")
            continue
        vec = []
        for c, cell, mech in r["verdict"]:
            v = result(cell)
            if v is None:
                bad("R3", f"{r['path'].name}: Verdict result `{plain(cell)}` for {c} is not pass, fail or "
                          "not evaluated")
            vec.append((v, mech))
        vectors[r["id"]] = vec
    rows = {}
    for rid, vals in comp["rows"]:
        if rid in rows:
            bad("R3", f"{cn}: {rid} has two rows in section 3")
        rows[rid] = vals
    for rid in comp["candidates"]:
        if rid not in rows:
            bad("R3", f"{cn}: candidate {rid} has no row in section 3")
        elif rid in vectors and comp["columns"] == crit:
            for c, cell, (want, _) in zip(crit, rows[rid] + [""] * len(crit), vectors[rid]):
                if result(cell) != want:
                    bad("R3", f"{cn}: {rid} × {c} is `{plain(cell) or 'empty'}`, the RUN's Verdict says "
                              f"`{want}`; copy it (COMPARISON rule 2)")
    for rid in rows:
        if rid not in comp["candidates"]:
            bad("R3", f"{cn}: section 3 row {rid} is not a candidate of section 2")

    # R4 — submission = selection
    sel = comp["selected"]
    pure = {rid: [v for v, _ in vec] for rid, vec in vectors.items()
            if all(v in ("pass", "fail") for v, _ in vec)}
    if sel is None:
        bad("R4", f"{cn}: section 5 has no `**Selected**: `<RUN ID>`` line")
    elif not sel.startswith("cpt-"):
        bad("R4", f"{cn}: nothing is selected (`{sel}`); no result can be submitted from this COMPARISON")
        sel = None
    elif sel not in comp["candidates"]:
        bad("R4", f"{cn}: selected {sel} is not a candidate of section 2")
        sel = None
    if sel is not None:
        info["selected"] = sel
        r = by_id.get(sel)
        vec = vectors.get(sel)
        if vec is not None:
            ne = [c for c, (v, _) in zip(crit, vec) if v == "not evaluated"]
            fl = [c for c, (v, m) in zip(crit, vec) if m and v == "fail"]
            if ne:
                bad("R4", f"selected {sel} has `not evaluated` rows ({', '.join(ne)}) and cannot be selected "
                          "(COMPARISON rule 2)")
            if fl:
                bad("R4", f"selected {sel} fails mechanical rows ({', '.join(fl)}); if no candidate passes every "
                          "mechanical gate, nothing is selected (COMPARISON rule 4)")
            for o, ov in pure.items():
                if o != sel and sel in pure and dominates(ov, pure[sel]):
                    bad("R4", f"selected {sel} is dominated by {o} (COMPARISON rule 3)")
        if r is not None:
            if r["sha"] is None or not SHA.fullmatch(r["sha"]):
                bad("R4", f"{r['path'].name}: section 3 has no `**Candidate sha256**:` of 64 hex digits; the "
                          "submission cannot be tied to the selected candidate")
            elif r["sha"] != sub_sha:
                bad("R4", f"the submission {Path(submission).name} has sha256 {sub_sha[:12]}…, the selected RUN "
                          f"{sel} records {r['sha'][:12]}…: the submitted file is not the selected candidate")

    # R5 — stopping rule
    head = comp["pairs_head"]
    pairs = [p for p in comp["pairs"] if any(plain(x) for x in p)
             and not (len([x for x in p if plain(x)]) == 1 and plain(p[0]).lower() in ("none", "—", "-"))]
    stat = next((k for k, h in enumerate(head or []) if h.startswith("status")), None)
    batches = {r["batch"]: r for r in (ds["rows"] if ds else [])}
    listed_pairs, open_pairs = set(), []
    if pairs and stat is None:
        bad("R5", f"{cn}: section 6 table has no Status column (`open` / `closed by batch <id>` / "
                  "`unresolvable: <reason>`)")
    for p in pairs:
        p = p + [""] * (len(head) - len(p))
        two = ids_in(p[0], "run")
        label = " vs ".join(two) if two else plain(p[0])
        if len(two) != 2:
            bad("R5", f"{cn}: section 6 pair `{plain(p[0])}` does not name two RUN IDs")
        else:
            for x in two:
                if x not in comp["candidates"]:
                    bad("R5", f"{cn}: section 6 pair {label} names {x}, not a candidate of section 2")
            listed_pairs.add(frozenset(two))
        if stat is None:
            continue
        s = plain(p[stat])
        m_closed = re.fullmatch(r"closed by batch\s+(\S+)", s, re.I)
        m_unres = re.fullmatch(r"unresolvable\s*:\s*(.*)", s, re.I | re.S)
        if s.lower() == "open":
            open_pairs.append(label)
        elif m_closed:
            b = m_closed.group(1).rstrip(".")
            row = batches.get(b)
            if row is None:
                bad("R5", f"{cn}: pair {label} is closed by batch {b}, which is not a batch of DATASET section 6")
            elif "information" not in row["justification"].lower():
                bad("R5", f"{cn}: pair {label} is closed by batch {b}, whose Justification has no "
                          "`information →` target; a batch closes a pair only if it was designed to separate it")
        elif m_unres:
            why = m_unres.group(1).strip()
            if not why:
                bad("R5", f"{cn}: pair {label} is `unresolvable` without a reason")
            elif NOT_A_REASON.search(why):
                bad("R5", f"{cn}: pair {label}: `{why}` is not a reason; fewer experiments is never a reason to "
                          "stop while a pair is separable within budget")
        else:
            bad("R5", f"{cn}: pair {label} has status `{s or 'empty'}`; use `open`, `closed by batch <id>` or "
                      "`unresolvable: <why the remaining budget cannot separate it>`")
    if info["selected"] and info["selected"] in pure:
        s_vec = pure[info["selected"]]
        for o, ov in pure.items():
            if o != info["selected"] and not dominates(s_vec, ov) and frozenset((o, info["selected"])) not in listed_pairs:
                bad("R5", f"{cn}: {o} is not dominated by the selected {info['selected']} and the pair is not in "
                          "section 6; list it with its status (COMPARISON rule 5)")
    for label in open_pairs:
        if budget_left is None:
            bad("R5", f"{cn}: pair {label} is open and the remaining budget is unknown; pass --budget-left "
                      "(0 when the budget is spent)")
        elif budget_left > 0:
            bad("R5", f"{cn}: pair {label} is open and {budget_left} batch(es) remain: run the batch that separates "
                      "it, or record `unresolvable: <why the remaining budget cannot separate it>`")
        else:
            notes.append(f"note: pair {label} stays open; the budget is spent")
    return fails, notes, info


# ── CLI ─────────────────────────────────────────────────────────

OPTS = ("--plan", "--dataset", "--runs", "--comparisons", "--submission", "--source", "--budget-left")
NEED = ("--plan", "--dataset", "--runs", "--comparisons", "--submission")


def parse(argv, allowed):
    o, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if a not in allowed or i + 1 >= len(argv) or a in o:
            raise ValueError(a)
        o[a] = argv[i + 1]
        i += 2
    if any(k not in o for k in NEED):
        raise ValueError("missing option")
    if "--budget-left" in o:
        if not re.fullmatch(r"\d+", o["--budget-left"].strip()):
            raise ValueError("--budget-left")
        o["--budget-left"] = int(o["--budget-left"])
    return o


def run_check(o):
    return check(o["--plan"], o["--dataset"], o["--runs"], o["--comparisons"], o["--submission"],
                 o.get("--source"), o.get("--budget-left"))


def hook(o) -> int:
    rec = {"time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds"), "gate": "result_gate",
           "version": VERSION, "gate_sha256": sha256_file(__file__), "verdict": None, "violations": [], "notes": [],
           "submission": o["--submission"], "submission_sha256": None, "comparison": None, "selected": None,
           "budget_left": o.get("--budget-left"), "source": o.get("--source"), "source_sha256": None}
    try:
        if o.get("--source"):
            rec["source_sha256"] = sha256_file(o["--source"])
        fails, notes, info = run_check(o)
        rec.update(info, verdict="PASS" if not fails else "FAIL", violations=fails, notes=notes)
    except (SourceError, OSError) as exc:
        rec.update(verdict="ERROR", violations=[f"result_gate: {exc}"])
    try:
        with open(o["--witness"], "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(", ", ": ")) + "\n")
    except OSError as exc:
        print(f"result_gate hook: result refused: cannot write the witness {o['--witness']}: {exc}", file=sys.stderr)
        return 2
    if rec["verdict"] == "PASS":
        for n in rec["notes"]:
            print(n)
        print("PASS")
        return 0
    for ln in rec["violations"] + rec["notes"]:
        print(ln, file=sys.stderr)
    print(f"result_gate hook: result refused: {rec['verdict']} — {len(rec['violations'])} violation(s)",
          file=sys.stderr)
    return 2


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["hook"]:
        try:
            o = parse(argv[1:], OPTS + ("--witness",))
            if "--witness" not in o:
                raise ValueError("--witness")
        except ValueError:
            print(__doc__)
            return 1
        return hook(o)
    try:
        o = parse(argv, OPTS)
    except ValueError:
        print(__doc__)
        return 2
    try:
        fails, notes, _ = run_check(o)
    except SourceError as exc:
        print(f"result_gate: {exc}", file=sys.stderr)
        return 2
    for f in fails + notes:
        print(f)
    print("PASS" if not fails else f"FAIL — {len(fails)} violation(s)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
