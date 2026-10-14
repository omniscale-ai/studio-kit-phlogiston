#!/usr/bin/env python3
"""Gate for LITERATURE artifacts. Stdlib only.
Exit 0 PASS, 1 FAIL, 2 usage error, 3 could not complete (network failure
after retries, HTTP 429/5xx, transport error, unreadable file).

    python3 scripts/lit_gate.py <file>.md [--plan <PLAN.md>] [--resolve]

Offline by default. --resolve looks every DOI up in OpenAlex (network).
--plan reads the PLAN's Literature mode and Excluded table (L11). Checks
L1-L11 are those of the "Gate rules" table in artifacts/LITERATURE/rules.md.
One line per violation `[Lk] message`, then PASS or FAIL - n violation(s).
"""
from __future__ import annotations

import csv
import datetime as dt
import http.client
import io
import json
import os
import re
import shlex
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lit_common import (DASHES, col_index, hit_index, load_plan, norm_doi, prose_of, section,  # noqa: E402
                        strip_cf, strip_md, strip_noncontent, table_list, table_rows, without_first_table)

STRATEGIES = ("related", "review", "metareview", "scout")
PLACEHOLDER = re.compile(r"^\s*\{", re.M)
RESOLVED = ("yes", "unresolved", "no doi")
BACKOFF = (1, 2)
DATE = r"\d{4}-\d{2}-\d{2}"


class ResolverError(Exception):
    """The resolver could not answer (transport error, 429, 5xx): not a verdict on the DOI."""


def openalex_resolver(doi: str):
    """Default resolver: OpenAlex record of a DOI as {'authors': [...], 'venue': str};
    None only on HTTP 404 (not resolved). Transport errors, 429 and 5xx are retried
    twice with backoff, then raise ResolverError."""
    url = (f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi)}"
           "?select=id,authorships,primary_location&mailto=kit-literature@example.org")
    err = ""
    for attempt in range(len(BACKOFF) + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "studio-kit lit_gate"})
            key = os.environ.get("OPENALEX_API_KEY")
            if key:
                req.add_header("Authorization", f"Bearer {key}")
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = f"HTTP {e.code}"
            if not (e.code == 429 or e.code >= 500):
                raise ResolverError(f"OpenAlex answered {err} for {doi}") from e
        except (OSError, ValueError, http.client.HTTPException) as e:
            err = f"{type(e).__name__}: {e}"
        if attempt < len(BACKOFF):
            time.sleep(BACKOFF[attempt])
    else:
        raise ResolverError(f"OpenAlex lookup of {doi} failed after retries ({err}); the DOI is not judged, rerun later")
    if not isinstance(d, dict):
        raise ResolverError(f"OpenAlex answered a non-object JSON for {doi}; the DOI is not judged, rerun later")
    if not d.get("id"):
        return None
    src = ((d.get("primary_location") or {}).get("source") or {})
    return {"authors": [(a.get("author") or {}).get("display_name") or "" for a in d.get("authorships") or []],
            "venue": src.get("display_name") or ""}


def valid_date(s: str) -> bool:
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def approval_ok(s: str) -> bool:
    """A person (at least two letters) and a YYYY-MM-DD date, no placeholder."""
    if "{" in s:
        return False
    m = re.search(DATE, s)
    if not m or not valid_date(m.group(0)):
        return False
    name = s.replace(m.group(0), "")
    bare = re.sub(r"[^a-z ]", "", name.lower()).strip()
    if bare in ("person", "name", "your name", "yyyy mm dd") or re.search(r"<[^>]*>", name):
        return False
    return len(re.findall(r"[^\W\d_]", name)) >= 2


def approval_who(s: str) -> tuple:
    """(person letters, date) of an approval string, for comparing two of them."""
    m = re.search(DATE, s)
    name = s.replace(m.group(0), "") if m else s
    return "".join(re.findall(r"[^\W\d_]", name.lower())), (m.group(0) if m else "")


def no_braces(s: str) -> str:
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\{[^{}]*\}", "", s)
    return s


MODE_LINE = re.compile(r"^\s*-?\s*Literature mode:\s*(.*)$", re.M | re.I)
MODE_TOKEN = re.compile(r"(none|allowed|blind)(?:$|, copied from\b.*$)", re.I)


def mode_lines(label_text: str) -> list:
    return MODE_LINE.findall(strip_md_lines(label_text))


def mode_of(label_text: str):
    """The Literature mode token of a Request (Markdown stripped), or None.
    After the token only the end of the line or the template tail
    `, copied from ...` is accepted; two mode lines give None."""
    lines = mode_lines(label_text)
    if len(lines) != 1:
        return None
    m2 = MODE_TOKEN.match(lines[0].strip())
    return m2.group(1).lower() if m2 else None


RAN_CELL = re.compile(r"(yes|no|not configured|skipped)(?:\s*\(.*\))?", re.I | re.S)


def ran_state(cell: str):
    """yes | no | not configured | skipped (+ optional parenthetical), else None."""
    m = RAN_CELL.fullmatch(strip_md(cell).strip())
    return m.group(1).lower() if m else None


def doc_invocation_ok(inv: str) -> bool:
    """lit_gate.py, exact --resolve, exact --plan followed by a path token."""
    try:
        toks = shlex.split(inv)
    except ValueError:
        return False
    if not any(t.endswith("lit_gate.py") for t in toks) or "--resolve" not in toks:
        return False
    return any(t == "--plan" and i + 1 < len(toks) and toks[i + 1] and not toks[i + 1].startswith("-")
               for i, t in enumerate(toks))


def strip_md_lines(t: str) -> str:
    return "\n".join(strip_md(ln) for ln in t.splitlines())


def raw_chunks(text: str) -> list:
    """(location, raw text) pieces of the whole file, nothing stripped: the
    frontmatter, the preamble before the first heading, then one piece per
    heading (named by its text, never by the matched content)."""
    out, rest = [], text
    fm = re.match(r"^---\n(.*?)\n---[ \t]*(?:\n|$)", text, re.S)
    if fm:
        out.append(("frontmatter", fm.group(1)))
        rest = text[fm.end():]
    name, buf = "preamble", []
    for ln in rest.split("\n"):
        h = re.match(r"^#{1,6}[ \t]+(?:\d+\.[ \t]*)?(.*)$", ln)
        if h:
            out.append((name, "\n".join(buf)))
            name, buf = f"section {h.group(1).strip()[:40]!r}" if not ln.startswith("# ") else "the title block", [ln]
        else:
            buf.append(ln)
    out.append((name, "\n".join(buf)))
    return out


def drop_real_table(chunk: str) -> str:
    """The Set chunk without the lines of its real (not commented, not fenced) first table."""
    real = [ln for ln in without_first_table_lines(strip_noncontent(chunk))]
    lines = chunk.replace("\r\n", "\n").split("\n")
    out = []
    for ln in lines:
        if ln in real:
            real.remove(ln)
            continue
        out.append(ln)
    return "\n".join(out)


def without_first_table_lines(stripped: str) -> list:
    """Lines of the first table of an already stripped section."""
    out, state = [], 0
    for ln in stripped.splitlines():
        is_t = ln.strip().startswith("|")
        if state == 0 and is_t:
            state = 1
        if state == 1:
            if is_t:
                out.append(ln)
            else:
                break
    return out


def passage_empty(pas: str) -> bool:
    pas = strip_cf(pas).strip()
    return not any(c.isalnum() for c in pas) or pas.lower() in ("none", "tbd", "null", "n/a")


def check(path, plan_path=None, do_resolve=False, resolver=None) -> list:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    resolver = resolver or openalex_resolver
    fails = []

    def bad(rule, msg):
        fails.append(f"[{rule}] {msg}")

    body = strip_noncontent(text)
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    status = "draft"
    if not fm:
        bad("L9", "no frontmatter: `status: draft|verified` is required")
    else:
        sm = re.search(r"^status:[ \t]*(.*)$", fm.group(1), re.M)
        if not sm:
            bad("L9", "frontmatter has no `status:` line; it must be draft or verified")
        else:
            val = sm.group(1).strip().strip("'\"").strip().lower()
            if val in ("draft", "verified"):
                status = val
            else:
                bad("L9", f"frontmatter status must be draft or verified, got {sm.group(1).strip()!r}")
    req = section(text, "Request")

    # L1
    m = re.search(r"^\s*-?\s*Strategy:(.*)$", req, re.M)
    scope = m.group(1) if m else req
    named = [s for s in STRATEGIES if re.search(rf"`{s}`", scope)]
    if len(named) != 1:
        bad("L1", f"section 1 names {len(named)} strategies; exactly one of {STRATEGIES} is required")
    strategy = named[0] if named else None

    # L2
    setsec = section(text, "Set")
    appr = re.search(r"^[ \t]*-[ \t]+Approved by:(.*)$", setsec, re.M)
    if not appr or not approval_ok(appr.group(1)):
        bad("L2", "the Set is not approved by a person (a name) with a date (YYYY-MM-DD)")
    att = section(text, "Attestation")
    if status == "verified":
        am = re.search(r"Set approved by\s+(.*)", att)
        if not am or not approval_ok(am.group(1)):
            bad("L2", "Attestation has no `Set approved by <person>, <date>` line")
        elif appr and approval_ok(appr.group(1)) and approval_who(appr.group(1)) != approval_who(am.group(1)):
            bad("L2", "section 3 `Approved by` and the Attestation `Set approved by` do not name the same person and date")

    # L3
    rows = table_rows(setsec, first_only=True)
    nset = len(rows)
    if nset == 0:
        bad("L3", "the Set table is empty")
    resolved_of, records = {}, {}
    unresolved_rows = []
    setnos = set()
    for r in rows:
        n0 = r[0].strip() if r else ""
        if re.fullmatch(r"[0-9]+", n0) and int(n0) > 0:
            if int(n0) in setnos:
                bad("L3", f"Set row number {n0} appears more than once in the `#` column")
            setnos.add(int(n0))
        else:
            bad("L3", f"Set row number {n0!r} is not a positive integer")
        if len(r) != 8:
            bad("L3", f"Set row {r[0] if r else '?'} has {len(r)} cells; exactly 8 are required")
            continue
        no, doi, res = r[0], strip_md(r[1]), strip_md(r[6]).lower()
        if n0.isdigit():
            resolved_of[int(n0)] = res
        if res not in RESOLVED:
            bad("L3", f"Set row {no}: resolved cell must be yes, unresolved or no DOI, got {r[6]!r}")
        if doi in DASHES:
            if res != "no doi":
                bad("L3", f"Set row {no}: no DOI and not marked `no DOI`")
        else:
            if res == "no doi":
                bad("L3", f"Set row {no}: has a DOI but is marked `no DOI`")
            if do_resolve:
                rec = resolver(norm_doi(doi))
                if rec is None:
                    if res != "unresolved":
                        unresolved_rows.append(no)
                else:
                    records[no] = rec
    if unresolved_rows:
        bad("L3", f"DOIs that do not resolve in OpenAlex on this run: rows {', '.join(unresolved_rows)} "
                  "(mark them `unresolved`; claims on them are `assumed`)")
    setrows = [r + [""] * (8 - len(r)) for r in rows]      # defensive padding for scanning

    # L4
    claims = table_rows(section(text, "Claims"))
    nclaims = len(claims)
    for i, r in enumerate(claims, 1):
        if len(r) < 5:
            bad("L4", f"Claims row {i} has fewer than 5 cells")
            continue
        _claim, setno, quote, loc, st = r[:5]
        st = st.strip().lower()
        if st not in ("verified", "assumed"):
            bad("L4", f"Claims row {i} status must be verified or assumed, got {r[4]!r}")
            continue
        setno = setno.strip()
        if setno and not (re.fullmatch(r"[0-9]+", setno) and int(setno) in setnos):
            bad("L4", f"Claims row {i} cites Set row {setno!r}, which does not exist (the Set rows are {sorted(setnos)})")
        if st == "verified":
            if quote.strip() in DASHES or loc.strip() in DASHES:
                bad("L4", f"Claims row {i} is `verified` without a quote and a location")
            if not re.fullmatch(r"[0-9]+", setno):
                bad("L4", f"Claims row {i} is `verified` without a Set row")
            elif resolved_of.get(int(setno)) != "yes":
                bad("L4", f"Claims row {i} is `verified` but Set row {setno} is not `resolved: yes`; it must be `assumed`")

    # L5: citations are read from prose outside tables and inline code, and from the
    # `set #` column of tables; passages, quotes and values are never scanned.
    ana = section(text, "Analysis")
    cited = set()

    def parse_cites(grp, where):
        for part in re.split(r"[,;]", grp):
            part = part.strip()
            m5 = re.fullmatch(r"(\d+)(?:\s*[\-–]\s*(\d+))?", part)
            if not m5:
                if part:
                    bad("L5", f"Analysis has the unparseable citation [{grp}] in {where}: a bracket holding a digit must be Set row "
                              "numbers separated by `,` or `;`, ranges as `a-b`; write other numbers or years "
                              "outside brackets, as ranges `0 to 1` or in parentheses")
                continue
            nums = [int(x) for x in m5.groups() if x]
            if len(nums) == 2 and nums[0] > nums[1]:
                bad("L5", f"Analysis cites the reversed range {part!r}")
            cited.update(nums)

    prose = prose_of(ana)
    for mm in re.finditer(r"\[([^\[\]]*)\]", prose):
        grp = mm.group(1)
        if not re.search(r"\d", grp) or prose[mm.end():mm.end() + 1] == "(":
            continue                                   # no digit, or a Markdown link
        parse_cites(grp, "the prose")
    for head, trows in table_list(ana):
        ci = col_index(head, "set #")
        if ci is None:
            continue
        for tr in trows:
            cell = tr[ci].strip() if ci < len(tr) else ""
            if cell in DASHES:
                continue
            parse_cites(cell.strip("[]"), "a `set #` cell")
    over = sorted(n for n in cited if n not in setnos)
    if over:
        bad("L5", f"Analysis cites Set rows that do not exist: {over}")
    if not ana.strip() or PLACEHOLDER.search(ana):
        if status == "verified":
            bad("L5", "Analysis is empty or still the placeholder")
    elif not cited:
        bad("L5", "Analysis cites no Set row; every assertion about a paper ends with its row in brackets")

    # L6
    hyp = section(text, "Candidate Hypotheses")
    hrows = table_rows(hyp)
    prose = "\n".join(ln for ln in no_braces(hyp).splitlines() if not ln.strip().startswith("|"))
    none_branch = bool(re.match(r"none\b", strip_md(prose).lower()))
    if not (none_branch and not hrows):
        if not hrows:
            bad("L6", "Candidate Hypotheses has neither rows nor `none`")
        for i, r in enumerate(hrows, 1):
            nums = [int(n) for n in re.findall(r"claim\s+(\d+)", r[1], re.I)] if len(r) >= 2 else []
            if len(r) < 4 or not nums or any(n < 1 or n > nclaims for n in nums):
                bad("L6", f"Candidate {i} cites no existing Claims row (`claim n`, 1 <= n <= {nclaims})")
            elif "NOT YET TESTED" not in r[3]:
                bad("L6", f"Candidate {i} status must be NOT YET TESTED here (it is confirmed only in a PLAN)")

    # sources (L7, L8, L11)
    srows = table_rows(section(text, "Sources"))
    hyp_ran = any(len(r) >= 2 and strip_md(r[0]).lower().startswith("hypothesis")
                  and ran_state(r[1]) == "yes" for r in srows)

    # L7 (the coverage threshold binds only a `verified` artifact; malformed text and
    # impossible or mismatching k of N fail for drafts too)
    col = strip_md(no_braces(section(text, "Collection"))).strip()
    kn = re.search(r"(\d+)\s+of\s+(\d+)", col)
    not_used = bool(re.match(r"not used\b", col, re.I))
    if not_used and not kn:
        if hyp_ran:
            bad("L7", "Sources says Hypothesis ran, but Collection says `not used`")
    elif not_used:
        bad("L7", "Collection says `not used` but also states a coverage `k of N`")
    elif not kn:
        bad("L7", "Collection is used but coverage is not stated as `k of N`")
    else:
        k, n = int(kn.group(1)), int(kn.group(2))
        if n == 0 or k > n:
            bad("L7", f"Collection coverage {k} of {n} is impossible (k must be <= N, N > 0)")
        elif n != nset:
            bad("L7", f"Collection says N = {n}, but the Set has {nset} rows; N must equal the number of Set rows")
        elif k < 0.5 * n and status == "verified":
            bad("L7", f"Collection covers {k} of {n} approved papers (< half): the map is of the uploads, not the subject")

    # L8
    for r in srows:
        if len(r) >= 2 and ran_state(r[1]) is None:
            bad("L8", f"source {r[0]}: the ran cell must be yes, no, not configured or skipped (<reason>; the reason is not gated), got {r[1]!r}")
        elif len(r) >= 3 and ran_state(r[1]) == "yes":
            qs = [q.strip() for q in re.split(r"<br\s*/?>", r[2]) if q.strip() not in DASHES]
            if not qs:
                bad("L8", f"source {r[0]} ran but records no query")

    # L10
    csv_text = ""
    if strategy == "scout":
        csvp = path.with_suffix(".csv")
        if csvp.exists():
            with open(csvp, newline="", encoding="utf-8-sig") as fh:
                csv_text = fh.read()
            rd = csv.reader(io.StringIO(csv_text, newline=""))
            head = [h.strip().lower() for h in next(rd, [])]
            if "value" not in head or "passage" not in head:
                bad("L10", f"{csvp.name} lacks a `value` or a `passage` column")
            else:
                iv, ip = head.index("value"), head.index("passage")
                csv_rows = [row for row in rd if any(c.strip() for c in row)]
                for i, row in enumerate(csv_rows, 1):
                    val = row[iv].strip() if iv < len(row) else ""
                    pas = row[ip].strip() if ip < len(row) else ""
                    if val and passage_empty(pas):
                        bad("L10", f"{csvp.name} row {i}: value without passage")
                stab = [(h, r) for h, r in table_list(ana) if col_index(h, "value") is not None
                        and col_index(h, "passage") is not None]
                if not stab:
                    if status == "verified":
                        bad("L10", "scout artifact has no scout table (columns `value` and `passage`) in section 5")
                for h, trs in stab:
                    tv, tp = col_index(h, "value"), col_index(h, "passage")
                    for i, row in enumerate(trs, 1):
                        val = row[tv].strip() if tv < len(row) else ""
                        pas = row[tp].strip() if tp < len(row) else ""
                        if val and val not in DASHES and passage_empty(pas):
                            bad("L10", f"section 5 scout table row {i}: value without passage")
                    if len(trs) != len(csv_rows):
                        bad("L10", f"section 5 scout table has {len(trs)} data rows, {csvp.name} has {len(csv_rows)}")
        else:
            bad("L10", "scout artifact has no CSV beside it")

    # L11
    req_mode = mode_of(req)
    if len(mode_lines(req)) > 1:
        bad("L11", "the Request has more than one `Literature mode:` line; exactly one is allowed")
    m = re.search(r"^\s*-?\s*\**PLAN\**:\s*`([^`]+)`", req, re.M)
    req_plan = m.group(1) if m else None
    if plan_path is None:
        if req_mode != "allowed":
            bad("L11", "without --plan the Request's Literature mode must be exactly `allowed` "
                       f"(got {req_mode!r}); other modes need --plan")
    else:
        plan = load_plan(plan_path)
        for p in plan["problems"]:
            bad("L11", p)
        if plan["mode"] == "none":
            bad("L11", "the PLAN's Literature mode is `none`: no LITERATURE may exist for it")
        if plan["id"] and req_plan != plan["id"]:
            bad("L11", f"Request PLAN is {req_plan!r}, the PLAN's ID is {plan['id']!r}")
        if plan["mode"] and req_mode != plan["mode"]:
            bad("L11", f"Request Literature mode is {req_mode!r}, the PLAN's is {plan['mode']!r}")
        if plan["mode"] == "blind":
            excl = plan["excluded"]
            if not excl:
                bad("L11", "the PLAN is `blind` with an empty Excluded table; it is not approvable")
            m = re.search(r"Exclusions checked:\s*(\d+)\b", strip_md(req))
            if not m:
                bad("L11", "Request `Exclusions checked` is not a number under a blind PLAN")
            elif int(m.group(1)) != len(excl):
                bad("L11", f"Exclusions checked is {m.group(1)}, the PLAN's Excluded table has {len(excl)} rows")

            def report(where, idx):
                bad("L11", f"excluded hit in {where} (PLAN Excluded row {idx + 1})")

            for r in setrows:
                i = hit_index(excl, dois=[r[1]], texts=[r[1]] + [c for j, c in enumerate(r) if j != 1],
                              link_texts=[r[7]])
                if i is not None:
                    report(f"Set row {r[0]}", i)
            h1 = re.search(r"^#\s+.*$", body, re.M)
            desc = re.search(r"^description:(.*)$", fm.group(1), re.M) if fm else None
            scans = [("section 3 outside the Set table", without_first_table(setsec), True),
                     ("Analysis", ana, True), ("Claims", section(text, "Claims"), True),
                     ("Candidate Hypotheses", hyp, True),
                     ("Request", req, True),
                     ("the title", h1.group(0) if h1 else "", True),
                     ("the frontmatter description", desc.group(1) if desc else "", True)]
            for name, sec_text, intext in scans:
                i = hit_index(excl, texts=[sec_text], doi_in_text=intext)
                if i is not None:
                    report(name, i)
            for where, chunk in raw_chunks(text):      # whole raw text, comments and fences included
                if where == "section 'Set'":           # the real table is scanned by cell, DOIs exactly
                    chunk = drop_real_table(chunk)
                i = hit_index(excl, texts=[chunk], doi_in_text=True)
                if i is not None:
                    report(f"the raw text of {where}", i)
            if csv_text:
                i = hit_index(excl, texts=[csv_text], doi_in_text=True)
                if i is not None:
                    report("the scout CSV beside the artifact", i)
            for r in srows:
                for cell in r[2:3]:
                    for q in re.split(r"<br\s*/?>", cell):
                        i = hit_index(excl, texts=[urllib.parse.unquote_plus(q), q], doi_in_text=True)
                        if i is not None:
                            report(f"Sources query of {r[0]}", i)
            if do_resolve:
                for no, rec in records.items():
                    meta = list(rec.get("authors") or []) + [rec.get("venue") or ""]
                    i = hit_index(excl, texts=meta)
                    if i is not None:
                        report(f"OpenAlex authors or venue of Set row {no}", i)

    # L9
    if status == "verified":
        others = [f for f in fails if not f.startswith("[L9]")]
        if others:
            bad("L9", "status is `verified` but L1-L8, L10 or L11 fail; set it back to `draft`")
        online = False
        for ln in att.splitlines():
            m = re.match(rf"^\s*[-*]?\s*Gate, online:\s*`([^`]*)`,\s*run\s+({DATE}):\s*(PASS|FAIL)\b", ln)
            if (m and valid_date(m.group(2)) and m.group(3) == "PASS"
                    and doc_invocation_ok(m.group(1))):
                online = True
        if not online:
            bad("L9", "status is `verified` but the Attestation has no `Gate, online: `<invocation>`, run YYYY-MM-DD: PASS` "
                      "line whose invocation has lit_gate.py, --resolve and --plan")
    return fails


def main(argv=None, resolver=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    plan, do_resolve, files = None, False, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--resolve":
            do_resolve = True
        elif a == "--plan":
            i += 1
            if i >= len(argv):
                print(__doc__)
                return 2
            plan = argv[i]
        elif a.startswith("-"):
            print(__doc__)
            return 2
        else:
            files.append(a)
        i += 1
    if len(files) != 1 or not Path(files[0]).is_file() or (plan is not None and not Path(plan).is_file()):
        print(__doc__)
        return 2
    try:
        fails = check(files[0], plan, do_resolve, resolver)
    except (OSError, UnicodeDecodeError, ResolverError, http.client.HTTPException) as e:
        print(f"lit_gate: cannot complete the check: {e}", file=sys.stderr)
        return 3
    for f in fails:
        print(f)
    print("PASS" if not fails else f"FAIL — {len(fails)} violation(s)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
