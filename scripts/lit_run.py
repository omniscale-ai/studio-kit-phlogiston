#!/usr/bin/env python3
"""Run the retrieval half of one literature strategy and write the draft
LITERATURE artifact. Stdlib only; OpenAlex REST, keyless (a free key in
OPENALEX_API_KEY raises the daily budget tenfold).

    python3 scripts/lit_run.py related    10.1016/j.ifacol.2017.08.071 --system ctank --plan architecture/PLAN.md
    python3 scripts/lit_run.py review     "cascaded tanks benchmark nonlinear system identification" --system ctank --since 2015 --depth deep --plan architecture/PLAN.md
    python3 scripts/lit_run.py metareview "nonlinear system identification" --system ctank --plan architecture/PLAN.md
    python3 scripts/lit_run.py scout      "Bouc-Wen hysteresis parameter identification" --system bw --quantity "hysteresis parameters" --unit "-" --plan architecture/PLAN.md

Writes <out>/<strategy>-<slug>.md (default out: architecture/literature) with
the Request lines Strategy, Anchor or Subject, Bounds, Depth, Output shape and
the two cost lines; section 2 Sources; section 3 Set; the section 4
placeholder; and the Retrieval line of section 8. For `scout` it also writes
the CSV skeleton beside the artifact, and nothing else: scout values never
become DATASET candidates (P1). The agent writes sections 5-7 over the Set.

--plan <PLAN.md> reads the PLAN's Literature mode and Excluded table before
any retrieval. Mode `none`: exit 2, nothing written. Mode `blind`: an anchor
or subject that matches an excluded item is refused (exit 2); retrieved
papers that match are dropped from the Set and counted, and the count is
written as `Removed by exclusion: <n>`. Matching is lit_common.hit_index,
the function the gate uses, here also applied to authors and venue. With
--plan the lines PLAN, Literature mode and Exclusions checked are filled from
the PLAN; without it they are left as the template's placeholders for the
agent. The fetched `related` anchor is checked too (title, authors, venue,
DOI) before any further request. Under blind a `review` Landscape and Groups
are computed from the kept papers only. The file name carries a short hash of
the query; an existing artifact or CSV is never overwritten without --force
(checked before any request). Exit codes: 0 written, 1 retrieval failed
(nothing written), 2 refused or usage.

--since and --depth are valid only for `review` (exit 2 before any request
for another strategy). For the other strategies -n caps the whole Set
(`related` fills references, citers, related, same-topic in that order after
removing duplicates, then truncates to n); the Depth line then records `-n <N>`.
The artifact and its CSV are written to temporary files and renamed, so a
failure leaves nothing half-written. Section 1 gets `Cost stated before
running: {the cost as stated to the human and approved}` for the agent to
fill, and `Cost used:` with the actual retrieval credits.

Why a script: the Set, the queries that produced it, the resolved flags and
the budget used are facts about a computation. Written by hand they drift
toward what the author hoped to find.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import shlex
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lit_common import hit_index, load_plan, norm_doi  # noqa: E402

VERSION = "0.2.0"
BASE = "https://api.openalex.org"
MAILTO = os.environ.get("OPENALEX_MAILTO", "kit-literature@example.org")
FIELDS = ("id,doi,title,publication_year,type,cited_by_count,primary_location,"
          "authorships,topics,abstract_inverted_index,referenced_works,related_works,best_oa_location")
MEASURE_WORDS = ("measured", "measurement", "experimental", "we report", "sample", "specimen",
                 "apparatus", "setup", "data set", "dataset", "benchmark", "recorded", "sensor",
                 "instrument", "calibrat")
REVIEW_WORDS = ("review", "survey", "overview", "tutorial", "road map", "roadmap", "perspective")

budget = {"credits": 0, "remaining": "?", "queries": []}


class Refused(Exception):
    """Intake refusal (rule 11): exit 2, nothing written."""


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

def get(path: str, **params) -> dict:
    params = {k: v for k, v in params.items() if v is not None}
    params["mailto"] = MAILTO
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"studio-kit literature {VERSION} (mailto:{MAILTO})"})
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=60) as r:
        budget["credits"] += int(r.headers.get("x-ratelimit-credits-used", 0) or 0)
        budget["remaining"] = r.headers.get("x-ratelimit-remaining", "?")
        budget["queries"].append(url.replace(f"&mailto={urllib.parse.quote(MAILTO)}", ""))
        return json.load(r)


def abstract(w: dict) -> str:
    inv = w.get("abstract_inverted_index") or {}
    return " ".join(t for _, t in sorted((p, t) for t, ps in inv.items() for p in ps))


def search(q: str, n: int, sort: str = "relevance_score:desc", **flt) -> list:
    f = ",".join(f"{k}:{v}" for k, v in flt.items()) or None
    out, page = [], 1
    while len(out) < n:
        # a fixed page size keeps the pages disjoint; the surplus is cut at the end
        d = get("/works", search=q, filter=f, select=FIELDS, per_page=50, page=page, sort=sort)
        out += d["results"]
        if len(d["results"]) < 50:
            break
        page += 1
    return out[:n]


def work(ident: str) -> dict:
    ident = ident if ident.startswith(("W", "https://")) else f"https://doi.org/{ident}"
    return get(f"/works/{ident}", select=FIELDS)


def by_ids(ids: list) -> list:
    out = []
    for i in range(0, len(ids), 50):
        chunk = "|".join(x.rsplit("/", 1)[-1] for x in ids[i:i + 50])
        out += get("/works", filter=f"openalex_id:{chunk}", select=FIELDS, per_page=50)["results"]
    return out


def citers(wid: str, n: int) -> list:
    return get("/works", filter=f"cites:{wid.rsplit('/', 1)[-1]}", select=FIELDS,
               per_page=min(n, 50), sort="cited_by_count:desc")["results"]


def grouped(q: str, by: str, **flt) -> list:
    f = ",".join(f"{k}:{v}" for k, v in flt.items()) or None
    d = get("/works", search=q, filter=f, group_by=by, per_page=25)
    return [(g["key"], g["key_display_name"], g["count"]) for g in d["group_by"]]


# ---------------------------------------------------------------------------
# strategies: each returns (rows, extra) — rows for the Set, extra per path
# ---------------------------------------------------------------------------

def dedupe(items: list) -> list:
    seen, out = set(), []
    for w, role in items:
        if w["id"] not in seen:
            seen.add(w["id"])
            out.append((w, role))
    return out


def s_related(anchor: str, n: int, excluded=None):
    a = work(anchor)
    if excluded:      # intake check on the fetched anchor, before any further call
        d, t = work_fields(a)
        if hit_index(excluded, dois=d, texts=t, link_texts=t[2:3], doi_in_text=True) is not None:
            raise Refused("the anchor matches an item of the PLAN's Excluded table")
    refs = sorted(by_ids(a.get("referenced_works") or []), key=lambda w: -(w.get("cited_by_count") or 0))
    cit = citers(a["id"], n)
    rel = by_ids(a.get("related_works") or [])
    same = [w for w in search(a["title"], n + 1) if w["id"] != a["id"]]
    items = ([(w, "reference") for w in refs[:n]] + [(w, "citer") for w in cit[:n]]
             + [(w, "related") for w in rel[:n // 2]] + [(w, "same-topic") for w in same[:n // 2]])
    return dedupe(items)[:n], {"anchor": a}


def s_review(subject: str, n: int, since, deep: bool, excluded=None):
    flt = {"publication_year": f">{since - 1}"} if since else {}
    ws = search(subject, n, **flt)
    pre = 0
    if excluded:      # never snowball from an excluded paper
        kept, pre = apply_exclusion([(w, "set") for w in ws], excluded)
        ws = [w for w, _ in kept]
    anchors = sorted(ws, key=lambda w: -(w.get("cited_by_count") or 0))[:10]
    items = [(w, "anchor" if w in anchors else "set") for w in ws]
    if deep:
        for a in anchors[:5]:
            items += [(w, "snowball") for w in citers(a["id"], 10)]
            items += [(w, "snowball") for w in by_ids((a.get("referenced_works") or [])[:10])]
    return dedupe(items), {"subject": subject, "flt": flt, "pre_removed": pre}


def author_groups(rows: list) -> list:
    """Authors by output in the given rows, with institutions and years."""
    auth = defaultdict(lambda: {"n": 0, "cites": 0, "years": set(), "inst": Counter(), "coauthors": Counter(), "works": []})
    for w, _ in rows:
        names = [((x.get("author") or {}).get("id"), (x.get("author") or {}).get("display_name") or "",
                  [i["display_name"] for i in x.get("institutions", [])]) for x in (w.get("authorships") or [])]
        for aid, name, inst in names:
            g = auth[(aid, name)]
            g["n"] += 1
            g["cites"] += w.get("cited_by_count") or 0
            g["years"].add(w.get("publication_year"))
            g["inst"].update(inst)
            g["works"].append(w["id"].rsplit("/", 1)[-1])
            for bid, bname, _ in names:
                if bid != aid:
                    g["coauthors"][bname] += 1
    return sorted(auth.items(), key=lambda kv: (-kv[1]["n"], -kv[1]["cites"]))[:15]


def local_counts(rows: list) -> dict:
    """Landscape counts computed from the kept rows only (no server-side group_by)."""
    c = {k: Counter() for k in ("publication_year", "primary_topic.id", "authorships.institutions.id", "primary_location.source.id")}
    for w, _ in rows:
        c["publication_year"][w.get("publication_year")] += 1
        top = w.get("primary_topic") or ((w.get("topics") or [{}])[0])
        if top.get("display_name"):
            c["primary_topic.id"][top["display_name"]] += 1
        for x in w.get("authorships") or []:
            for i in x.get("institutions", []):
                c["authorships.institutions.id"][i["display_name"]] += 1
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        if src:
            c["primary_location.source.id"][src] += 1
    return {k: [(d, d, n) for d, n in v.most_common(12)] for k, v in c.items()}


def review_extra(rows: list, extra: dict, blind: bool) -> dict:
    """Groups and Landscape for the review, from the kept rows. Under blind the
    Landscape is recomputed locally from them; the server-side group_by counts
    and the total match count cannot be filtered per work and are not used."""
    subject, flt = extra["subject"], extra["flt"]
    if blind:
        counts, n_total = local_counts(rows), None
    else:
        counts = {k: grouped(subject, k, **flt)[:12] for k in
                  ("publication_year", "primary_topic.id", "authorships.institutions.id", "primary_location.source.id")}
        n_total = get("/works", search=subject, filter=",".join(f"{k}:{v}" for k, v in flt.items()) or None,
                      per_page=1)["meta"]["count"]
    return {"groups": author_groups(rows), "counts": counts, "n_total": n_total, "pre_removed": extra.get("pre_removed", 0)}


def s_metareview(subject: str, n: int):
    topics = "|".join(k.rsplit("/", 1)[-1] for k, _, _ in grouped(subject, "primary_topic.id")[:4])
    flt = {"title_and_abstract.search": subject, "primary_topic.id": topics}
    typed = search(subject, n, type="review", **flt)
    titled = [w for w in search(f"{subject} review OR survey", n, **flt)
              if any(k in (w.get("title") or "").lower() for k in REVIEW_WORDS)]
    rows = dedupe([(w, "review") for w in typed + titled])
    rows.sort(key=lambda r: -(r[0].get("cited_by_count") or 0))
    return rows[:n], {"topics": topics}


def s_scout(subject: str, n: int):
    ws = [w for w, _ in dedupe([(w, "") for w in search(subject, n)])]
    scored = []
    for w in ws:
        a = abstract(w).lower()
        hits = [k for k in MEASURE_WORDS if k in a]
        scored.append((w, hits))
    scored.sort(key=lambda x: (-len(x[1]), -(x[0].get("publication_year") or 0)))
    return [(w, f"candidate ({len(h)} signals)") for w, h in scored][:n], {}


# ---------------------------------------------------------------------------
# exclusion (rule 11): same matching function as the gate
# ---------------------------------------------------------------------------

def work_fields(w: dict) -> tuple:
    """(dois, texts) of a retrieved work: DOI, title, OA link, venue, authors,
    institution names and topic names (the screened fields)."""
    doi = norm_doi(w.get("doi") or "")
    src = ((w.get("primary_location") or {}).get("source") or {})
    authors = [(x.get("author") or {}).get("display_name") or "" for x in (w.get("authorships") or [])]
    insts = [i.get("display_name") or "" for x in (w.get("authorships") or []) for i in (x.get("institutions") or [])]
    topics = [t.get("display_name") or "" for t in ([w.get("primary_topic") or {}] + list(w.get("topics") or []))]
    return [doi], [doi, w.get("title") or "", oa(w), src.get("display_name") or ""] + authors + insts + topics


def apply_exclusion(rows: list, excluded: list) -> tuple:
    """Drop rows that hit an excluded item. Returns (kept, number_removed)."""
    kept = []
    for w, role in rows:
        dois, texts = work_fields(w)
        if hit_index(excluded, dois=dois, texts=texts, link_texts=texts[2:3]) is None:
            kept.append((w, role))
    return kept, len(rows) - len(kept)


def check_plan(plan_path, query: str):
    """Read the PLAN before any retrieval. Returns (plan, None) or (None, message)."""
    plan = load_plan(plan_path)
    if plan["problems"]:
        return None, "; ".join(plan["problems"])
    if plan["mode"] == "none":
        return None, "the PLAN's Literature mode is `none`: no literature is searched and no LITERATURE is produced"
    if plan["mode"] == "blind":
        if not plan["excluded"]:
            return None, "the PLAN is `blind` with an empty Excluded table; it is not approvable"
        if hit_index(plan["excluded"], dois=[query], texts=[query], doi_in_text=True) is not None:
            return None, "the anchor or subject matches an item of the PLAN's Excluded table; refused at intake"
    return plan, None


# ---------------------------------------------------------------------------
# the draft artifact
# ---------------------------------------------------------------------------

def slugify(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:60]


def artifact_slug(strategy: str, query: str) -> str:
    """Readable prefix plus a short hash of the full query, so two long queries never collide."""
    return f"{slugify(f'{strategy}-{query}')}-{hashlib.sha1(query.encode('utf-8')).hexdigest()[:8]}"


def oa(w):
    o = w.get("best_oa_location") or {}
    return o.get("pdf_url") or o.get("landing_page_url") or ""


def set_table(rows: list) -> str:
    lines = ["| # | DOI | year | title | role | cited by | resolved | OA link |",
             "|---|-----|------|-------|------|----------|----------|---------|"]
    for i, (w, role) in enumerate(rows, 1):
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        lines.append(f"| {i} | {doi or '—'} | {w.get('publication_year') or '—'} | "
                     f"{(w.get('title') or '').replace('|', chr(92) + '|')[:120]} | {role} | {w.get('cited_by_count') or 0} | "
                     f"{'yes' if doi else 'no DOI'} | {oa(w).replace('|', chr(92) + '|')} |")
    return "\n".join(lines)


def groups_table(groups: list) -> str:
    lines = ["| author | works in set | citations | years | institutions | frequent co-authors | works |",
             "|--------|--------------|-----------|-------|--------------|---------------------|-------|"]
    for (aid, name), g in groups:
        yrs = sorted(y for y in g["years"] if y)
        name = name.replace("|", "\\|")
        lines.append(f"| {name} | {g['n']} | {g['cites']} | {yrs[0] if yrs else '—'}–{yrs[-1] if yrs else '—'} | "
                     f"{'; '.join(k for k, _ in g['inst'].most_common(2))} | "
                     f"{'; '.join(k for k, _ in g['coauthors'].most_common(3))} | {', '.join(g['works'][:6])} |")
    return "\n".join(lines)


def counts_block(counts: dict) -> str:
    out = []
    for k, v in counts.items():
        out.append(f"- **{k}**: " + "; ".join(f"{d}: {c}" for _, d, c in v))
    return "\n".join(out)


PLACEHOLDER = {
    "related": "{Path 1: group the references by the sub-problem they address; for each, what was established, by whom, with which method, and what the anchor adds. Every assertion cites a Set row in brackets; the anchor is named without a row.}",
    "review": "{Path 2: one block per group (authors, institutions, approach, data, years active, achievements in the Set's own terms, assessment succeeding / stalled / too early with cited evidence), then the cross-group observations: agreement, contradiction, gaining and abandoned approaches by year. Start from the Groups table in section 3; merge or split groups and say why.}",
    "metareview": "{Path 3: per review its scope, period, trends asserted and gaps named; then trends asserted by several reviews, trends contradicted between reviews, what no review covers. No primary-source claim; a claim that needs one is listed as a candidate for Path 1 or 2.}",
    "scout": "{Path 4: the scout table from the CSV beside this artifact, one row per measurement: set # | paper | doi | link | what_measured | how_measured | constraints (in the paper's words) | value | unit | passage. No passage, no value. Units as printed. Values are claims, never a DATASET.}",
}


def write_artifact(strategy, query, system, rows, extra, args, out_dir: Path, plan=None, removed=0, argv=None) -> Path:
    today = dt.date.today().isoformat()
    slug = artifact_slug(strategy, query)
    out = out_dir / f"{slug}.md"
    anchor = extra.get("anchor")
    title = (anchor or {}).get("title") if anchor else query
    queries = list(dict.fromkeys(budget["queries"])) or ["—"]
    sec3_extra = ""
    if strategy == "review":
        landscape = (f"{extra['n_total']} works match the query in OpenAlex; the Set holds {len(rows)}"
                     if extra.get("n_total") is not None else f"computed from the {len(rows)} works of the Set")
        sec3_extra = (f"\n\n**Landscape** ({landscape}):\n\n"
                      + counts_block(extra["counts"]) + "\n\n**Groups** (by output in the Set; co-authorship suggests the grouping, the human confirms it):\n\n"
                      + groups_table(extra["groups"]))
    csv_path = out.with_suffix(".csv")
    if strategy == "scout":
        sec3_extra = f"\n\nExtraction skeleton written to `{csv_path.name}` (one row per paper; add rows per measurement)."
    if plan:
        blind = plan["mode"] == "blind"
        plan_lines = (f"- PLAN: `{plan['id']}`\n"
                      f"- Literature mode: `{plan['mode']}`, copied from the PLAN's section 2.\n"
                      f"- Exclusions checked: {len(plan['excluded']) if blind else 'not applicable'}\n")
        removed_line = f"- Removed by exclusion: {removed if blind else 'not applicable'}\n"
    else:
        plan_lines = ("- PLAN: `cpt-{system}-plan-{slug}`\n"
                      "- Literature mode: {`allowed` | `blind`, copied from the PLAN's section 2}\n"
                      "- Exclusions checked: {number of rows of the PLAN's Excluded table under `blind`; `not applicable` under `allowed`}\n")
        removed_line = "- Removed by exclusion: {under `blind` the count only; `not applicable` under `allowed`}\n"
    anchor_line = ("Anchor: " + (anchor.get("doi") or anchor["id"])) if anchor else "Subject: " + query
    bounds = (f"since {args.since}" if strategy == "review" and args.since else "no year bound") + (
        f"; quantity {args.quantity} [{args.unit or '?'}]" if strategy == "scout" else "") + "."
    key = "keyed" if os.environ.get("OPENALEX_API_KEY") else "keyless"
    toks = [t.replace("`", "'").replace("\n", " ") for t in (argv if argv is not None else sys.argv)]
    cmd = shlex.join(["python3"] + toks)
    depth_line = args.depth if strategy == "review" else f"-n {args.n}"
    openalex_rows = "\n".join(
        f"| OpenAlex | yes | {q.replace('|', chr(92) + '|')} | " + (f"{budget['credits']} credits | {len(budget['queries'])} requests; {key}" if k == 0
                                                       else f"— | request {k + 1} of {len(queries)} distinct") + " |"
        for k, q in enumerate(queries))
    doc = f"""---
description: {json.dumps(f'{strategy} on "{title}": {len(rows)} papers in the set, 0 claims verified (draft)', ensure_ascii=False)}
status: draft
---

# LITERATURE — {strategy}: {title}

**ID**: `cpt-{system}-literature-{slug}`

## Table of Contents

<!-- generated by `cfs toc` -->

## 1. Request

{plan_lines}- Strategy: `{strategy}`
- {anchor_line}
- Bounds: {bounds}
- Depth: {depth_line}
- Output shape: {args.output}.
- Cost stated before running: {{the cost as stated to the human and approved}}
- Cost used: {budget['credits']} OpenAlex credits for retrieval ({len(budget['queries'])} requests; {budget['remaining']} remaining today); the online gate's DOI lookups are added when it runs.

## 2. Sources

| source | ran | query or tool calls | budget used | note |
|--------|-----|---------------------|-------------|------|
{openalex_rows}
| Consensus | {'not configured' if not os.environ.get('CONSENSUS_API_KEY') else 'no'} | — | 0 | {'set CONSENSUS_API_KEY to enable' if not os.environ.get('CONSENSUS_API_KEY') else 'available; run after set approval'} |
| Hypothesis | {'not configured' if not os.environ.get('HYPOTHESIS_MCP_KEY') else 'no'} | — | — | {'set HYPOTHESIS_MCP_KEY and build a collection of the approved set' if not os.environ.get('HYPOTHESIS_MCP_KEY') else 'available; build the collection after set approval'} |

{removed_line}
## 3. Set

{set_table(rows)}{sec3_extra}

- Approved by: {{person, YYYY-MM-DD}}

## 4. Collection

not used

## 5. Analysis

{PLACEHOLDER[strategy]}

## 6. Claims

| claim | set # | quote | location | status |
|-------|-------|-------|----------|--------|

## 7. Candidate Hypotheses

{{one candidate per contradiction in the Set, or `none`}}

| candidate | claims | proposed diagnostic condition | status |
|-----------|--------|-------------------------------|--------|

## 8. Attestation

- Retrieval: `{cmd}`, run {today}; `scripts/lit_run.py` {VERSION}, OpenAlex REST {key} (`{BASE}`), {len(budget['queries'])} requests, {budget['credits']} credits.
"""
    out_dir.mkdir(parents=True, exist_ok=True)
    finals = [(out, doc)]
    if strategy == "scout":
        buf = io.StringIO(newline="")
        wr = csv.writer(buf)
        wr.writerow(["set_no", "paper", "doi", "link", "what_measured", "how_measured", "constraints", "value", "unit", "passage"])
        for i, (w, _) in enumerate(rows, 1):
            wr.writerow([i, w.get("title"), (w.get("doi") or "").replace("https://doi.org/", ""), oa(w), "", "", "", "", args.unit or "", ""])
        finals.append((csv_path, buf.getvalue()))
    tmps, created = [], []
    try:
        for dest, content in finals:
            tmp = dest.with_name(dest.name + ".tmp")
            tmps.append(tmp)
            with open(tmp, "w", newline="", encoding="utf-8") as fh:
                fh.write(content)
        for (dest, _), tmp in zip(finals, tmps):
            existed = dest.exists()
            os.replace(tmp, dest)
            if not existed:
                created.append(dest)
    except BaseException:
        for t in tmps + created:      # nothing half-written is left behind
            try:
                t.unlink()
            except OSError:
                pass
        raise
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("strategy", choices=["related", "review", "metareview", "scout"])
    ap.add_argument("query", help="DOI / OpenAlex id for related; subject otherwise")
    ap.add_argument("--system", required=True)
    ap.add_argument("--out", default="architecture/literature")
    ap.add_argument("--plan", help="PLAN.md: reads Literature mode and the Excluded table")
    ap.add_argument("-n", type=int, default=None, help="non-review: cap on the total Set; review: search size per query, not recorded in Depth (default by depth)")
    ap.add_argument("--since", type=int, help="review only: earliest publication year")
    ap.add_argument("--depth", choices=["quick", "deep"], default=None, help="review only (default quick)")
    ap.add_argument("--quantity", default="")
    ap.add_argument("--unit", default="")
    ap.add_argument("--output", default="reading list")
    ap.add_argument("--force", action="store_true", help="overwrite an existing artifact and CSV")
    a = ap.parse_args(argv)
    if a.strategy != "review":
        for flag, val in (("--since", a.since), ("--depth", a.depth)):
            if val is not None:
                print(f"lit_run: refused: {flag} is valid only for `review`; for {a.strategy} use -n to cap the Set", file=sys.stderr)
                return 2
    if a.n is not None and a.n < 1:
        print("lit_run: refused: -n must be a positive integer", file=sys.stderr)
        return 2
    a.depth = a.depth or "quick"
    plan = None
    if a.plan is not None:
        if not Path(a.plan).is_file():
            print(f"lit_run: PLAN not found: {a.plan}", file=sys.stderr)
            return 2
        plan, err = check_plan(a.plan, a.query)       # before any retrieval
        if err:
            print(f"lit_run: refused: {err}", file=sys.stderr)
            return 2
    a.n = a.n or (20 if a.depth == "quick" else 100)
    n = a.n
    out_dir = Path(a.out)
    slug = artifact_slug(a.strategy, a.query)
    written = [out_dir / f"{slug}.md"] + ([out_dir / f"{slug}.csv"] if a.strategy == "scout" else [])
    clash = [p for p in written if p.exists()]
    if clash and not a.force:
        print(f"lit_run: refused: {clash[0]} exists; rerun with --force to overwrite", file=sys.stderr)
        return 2
    blind = bool(plan and plan["mode"] == "blind")
    excluded = plan["excluded"] if blind else None
    budget.update(credits=0, remaining="?", queries=[])
    try:
        if a.strategy == "related":
            rows, extra = s_related(a.query, n, excluded)
        elif a.strategy == "review":
            rows, extra = s_review(a.query, n, a.since, a.depth == "deep", excluded)
        elif a.strategy == "metareview":
            rows, extra = s_metareview(a.query, n)
        else:
            rows, extra = s_scout(a.query, n)
        removed = extra.get("pre_removed", 0)
        if blind:
            rows, r2 = apply_exclusion(rows, excluded)
            removed += r2
        if a.strategy == "review":
            extra = review_extra(rows, extra, blind)
    except Refused as e:
        print(f"lit_run: refused: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # network or API failure: write nothing
        print(f"lit_run: retrieval failed: {e}", file=sys.stderr)
        return 1
    try:
        path = write_artifact(a.strategy, a.query, a.system, rows, extra, a, Path(a.out), plan, removed,
                              argv=sys.argv if argv is None else ["lit_run.py"] + list(argv))
    except OSError as e:
        print(f"lit_run: cannot write the artifact: {e}", file=sys.stderr)
        return 1
    print(f"{a.strategy}: {len(rows)} papers in the set ({removed} removed by exclusion) -> {path}  ({budget['credits']} credits, {budget['remaining']} left today)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
