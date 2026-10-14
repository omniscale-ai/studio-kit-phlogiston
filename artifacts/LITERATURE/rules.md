# LITERATURE Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{literature_template}` — structural reference
- `{literature_workflow}` — the four strategies; a LITERATURE is produced only by running one
- `{plan_template}` — section 2 of the PLAN: the literature mode and the Excluded table
- `{lit_run}` — retrieval: writes the draft artifact (rule 12)
- `{lit_gate}` — the gate: checks L1–L11 (rule 10)

---

1. **One LITERATURE is one request along one strategy.** `related`,
   `review`, `metareview` or `scout`, named in section 1. A request that
   needs two strategies is two artifacts. A search that followed no strategy
   is not recorded as a LITERATURE.
2. **The Set is the universe.** Section 3 lists every paper the analysis may
   cite; a paper outside it is not mentioned. Every assertion about a paper
   cites its Set row. The request's anchor is named without a row number;
   every other paper is cited by Set row. A Set row's number is its `#`
   cell: a unique positive integer; numbers need not be contiguous, and
   trimming the Set deletes rows without renumbering the rest, so a
   citation keeps pointing at the same paper. The Set is approved by a
   person before analysis starts (P12), and the approval is recorded with
   name and date. When the status is `verified`, the Attestation's
   `Set approved by` line names the same person and date (L2).
3. **A DOI that does not resolve is not a reference.** Section 3 marks each
   row's `resolved` cell `yes`, `unresolved` or `no DOI` (DOI cell `—`).
   With `--resolve` the gate fails a row whose DOI does not resolve unless
   its cell says `unresolved`; a row marked `unresolved` or `no DOI` does not
   block `verified`, but every Claims row citing it must be `assumed` (the
   gate fails a `verified` claim on such a row). Nothing is removed
   silently (L3, L4).
4. **A claim is a quote with a location.** Section 6 carries the paper's
   words and where they were found on this run, and the claim says no more
   than the quote shows. Without both, the status is `assumed`, and an
   assumed claim licenses no range and no mechanism (P10). Claims row n is
   the n-th data row of the Claims table, counted from 1 in table order;
   rows are never reordered or deleted after a PLAN cites them. Citations
   read `<LITERATURE ID>, claim n`.
5. **Sources are stated, including the ones that did not run.** Section 2
   gives each source's `ran` cell as `yes`, `no`, `skipped (<reason>)` or
   `not configured`, and a `yes` row records the query that can be rerun.
   A source substituted for another is a deviation and is written as one.
6. **A collection is not the subject.** When Hypothesis ran, section 4
   states as `k of N` how many of the approved set its collection holds,
   N being the number of Set rows and k ≤ N. A `draft` may record coverage
   below half; the artifact cannot become `verified` with it, because the
   claims map then describes the uploads, not the field (L7).
7. **No value without a passage; a value from a paper stays a claim.** In
   `scout`, a row carries a value only with the passage it came from (L10);
   units are copied as printed and converted only in a PLAN concordance
   (P2). The scout table stays in section 5 of the LITERATURE, with the same
   rows as CSV beside it, and cites its paper in its `set #` column. A value
   reaches a PLAN only as a claim cited in the PLAN's section 2 (P10): a
   `verified` claim may license a parameter range or a mechanism; an
   `assumed` claim is handed over as `assumed` and may motivate a
   diagnostic batch only. A value never becomes a DATASET: there is no
   `literature` origin, a RUN never fits it, and it is never pooled with
   measurements (P1).
8. **Analysis is written over the Set and in the strategy's shape.** Path 1
   (`related`) writes the prior work grouped by sub-problem and what the
   anchor adds; Path 2 (`review`) writes groups by named authors with an
   assessment and its evidence; Path 3 (`metareview`) writes trends from
   reviews and makes no primary-source claim; Path 4 (`scout`) writes one
   row per measurement. The shape is not negotiable per run; it is what
   makes the four outputs comparable across runs. Citations `[n]` are read
   only from Analysis prose outside tables and code; a section 5 table
   cites by its `set #` column, and its other cells (verbatim passages and
   quotes) are not read as citations.
9. **Hypotheses are proposed here, confirmed in the PLAN.** Section 7 rows
   are candidates that cite Claims rows as `claim n`, with a proposed
   diagnostic condition and status NOT YET TESTED. A candidate whose cited
   claims are all `assumed` is marked `assumed only`: it may motivate a
   diagnostic batch, and it is not proposed for the PLAN's section 8 as a
   mechanism (P10; the gate does not check the mark). Thresholds found in
   the literature are `proposed` (P7). Section 1 records the PLAN the
   request serves and the literature mode it ran under, copied from that
   PLAN. The PLAN cites the LITERATURE id; the LITERATURE never cites a
   PLAN's results.
10. **`verified` requires an attested online PASS against the PLAN; the
    gate checks the attestation, not that the run happened.** `{lit_gate}`
    runs its structural checks on every invocation; `--resolve` also looks
    up every DOI in OpenAlex; `--plan <PLAN.md>` reads the PLAN's Literature
    mode and Excluded table (rule 11). A LITERATURE becomes `verified` only
    after a PASS of an online invocation that has both `--resolve` and
    `--plan` (L9). An offline run without `--plan` is a structural check
    only: it leaves the status `draft` and never clears blind compliance.
    The Attestation records each invocation exactly as run, in the
    template's line form, with its result and date. Of the Attestation the
    gate reads only the `Set approved by` line (L2, when the status is
    `verified`) and the `Gate, online:` lines (L9); the other lines are for
    the record. An edit after a gate run is recorded in the Attestation and
    the gate is rerun.
11. **The PLAN's mode bounds the literature; blind runs exclude by the
    PLAN's list.** The PLAN's section 2 sets the literature mode. `none`: no
    literature is searched and no LITERATURE is produced; materials a human
    attached in the run's `literature` field remain allowed, marked `given`
    in the PLAN, and are the only literature that PLAN may cite; the
    workflow refuses to run. `allowed`: besides the attached materials,
    literature enters the PLAN only through LITERATURE artifacts. `blind`:
    as `allowed`, plus the PLAN's Excluded table lists items that must not
    be retrieved or cited because they could reveal the answer, each typed
    `doi`, `title`, `term`, `benchmark` or `author`; attached materials are
    checked against the Excluded table by the human at Approval (the gate
    does not see them). The person's confirmation of the mode, and under
    `blind` of the Excluded table, is recorded in the Attestation in the
    template's line form,
    `Literature mode confirmed by <person>, <YYYY-MM-DD> (<PLAN section 11 | conversation>)`,
    under `blind` followed by `; Excluded table confirmed`; the gate does
    not check this line. Matching is case-insensitive
    throughout: a `doi` item matches a DOI cell exactly, after any
    `https://doi.org/` prefix is stripped from both, and matches a DOI
    embedded in an OA link; in free text it matches as a substring; a
    `title`, `term`, `benchmark` or `author` item matches as a substring.
    The gate matches only with `--plan` under `blind`, since the Excluded
    table comes from the PLAN. It then compares the items with every cell
    of every Set row; with Analysis, Claims, Candidate Hypotheses and the
    Request; with each query of the Sources query column, also URL-decoded
    (a query that contains an excluded item means it was retrieved); with
    the H1 title and the frontmatter description; with section 3 outside
    the Set table; under `scout` with the CSV beside the artifact; and with
    the whole raw text of the file, HTML comments and code fences
    included. Venue and authors are not Set columns and
    are compared only with `--resolve`, against the OpenAlex record of each
    row that has a DOI. An offline PASS under `blind` therefore does not
    clear `author` items; only the online PASS with `--plan` does. An anchor
    that matches an excluded item is refused at intake. A matched paper is
    removed from the Set before approval, and section 2 gives the number
    removed, never the matched text; Analysis never names it. With `--plan`
    the gate fails if the PLAN's mode is `none`, if the Request's `PLAN:` ID
    differs from the PLAN's ID, if the Request's Literature mode differs
    from the PLAN's, and, under `blind`, on any excluded hit or if
    `Exclusions checked` differs from the PLAN's Excluded row count (L11).
    Without `--plan` L11 passes only when the Request's Literature mode is
    exactly `allowed`; `blind` and any other value fail. The PLAN's
    `LITERATURE drawn on` line is not checked by the gate; keeping it
    complete is the PLAN author's duty at Approval.
12. **Retrieval is a script run, recorded as run.** `{lit_run}` writes the
    mechanical parts of the draft (the template's opening comment lists
    them) and the Retrieval line of the Attestation; the agent does not
    write them by hand. `--since` and `--depth` apply only to `review`
    (exit 2 otherwise); for the other strategies `-n` caps the total Set.
    Under `blind` the cap applies before exclusion, so the Set may hold
    fewer than `-n` papers; removed papers are counted, not replaced.
    Bounds records only the bounds applied; Depth records `quick` or `deep`
    for `review` and `-n <N>` otherwise. `Cost stated before running` is
    the agent's estimate, written before the run (OpenAlex credits: search
    10, work 1, group_by 10, title search 10, online gate 1 per DOI);
    `Cost used` is written by `{lit_run}` for retrieval and completed by the
    agent with the gate's DOI lookups. `{lit_run}` refuses (exit 2, before
    any request) to overwrite an existing artifact or CSV unless `--force`
    is given.

## Gate rules (`{lit_gate}`)

`python3 {lit_gate} <file>.md [--plan <PLAN.md>] [--resolve]`; exit 0
PASS, 1 FAIL, 2 usage error, 3 could not complete (network or file
error; no verdict). Every invocation runs all checks it can; `--resolve`
adds the OpenAlex lookups, `--plan` the PLAN checks.

| ID | The gate fails the artifact unless |
|----|------------------------------------|
| L1 | section 1 names exactly one of the four strategies (rule 1) |
| L2 | the Set is approved by a person with a date; when the status is `verified`, the Attestation also has the `Set approved by` line naming the same person and date as section 3 (rule 2) |
| L3 | every Set row has 8 cells and a `#` that is a positive integer not used by another row (contiguity not required); every row has a DOI or the DOI cell `—` with `no DOI`; every `resolved` cell is `yes`, `unresolved` or `no DOI`; with `--resolve`, every DOI looked up resolves unless its cell says `unresolved` (rules 2, 3) |
| L4 | every `verified` claim has a quote and a location and cites a Set row whose `resolved` cell is `yes`; any other claim is `assumed` (rules 3, 4) |
| L5 | the citations `[n]` of the Analysis prose, read outside tables and code, name existing Set `#` values, and the Analysis cites at least one; in a section 5 table the `set #` column names an existing Set row, and the other cells are not read; the anchor is exempt (rules 2, 8) |
| L6 | every Candidate Hypotheses row cites existing Claims rows as `claim n` and has status NOT YET TESTED, or the section says `none` (rule 9) |
| L7 | Collection says `not used`, or gives `k of N` with N the number of Set rows and k ≤ N; when the status is `verified`, also k/N ≥ 0.5 (rule 6) |
| L8 | every source's `ran` cell is `yes`, `no`, `skipped (<reason>)` or `not configured`, and every source marked `yes` records its query (rule 5) |
| L9 | status `verified` only if L1–L8, L10 and L11 pass and the Attestation records an `online` PASS whose invocation has `--resolve` and `--plan`; an offline run on a `verified` file fails L9 when no such Attestation line exists (rule 10) |
| L10 | under `scout`, the CSV beside the artifact and the section 5 scout table have the same number of rows, and in both every value carries its passage; under `blind` with `--plan` the CSV is also compared with the Excluded items (rules 7, 11) |
| L11 | with `--plan`: the PLAN's mode is not `none`, the Request's `PLAN:` ID and Literature mode equal the PLAN's, and under `blind` there is no excluded hit and `Exclusions checked` equals the PLAN's Excluded row count; without `--plan`: the Request's Literature mode is exactly `allowed` (rule 11) |

## Where the principles land in a LITERATURE

| Section | Principles |
|---------|------------|
| 1. Request | P12 literature mode set by a person in the PLAN and copied here; rule 11 exclusions checked under `blind`, compared with the PLAN by the gate; P3 cost stated by the agent before running and cost used, retrieval and gate lookups together (rule 12) |
| 2. Sources | P3 budget used per source; honesty about what ran; rule 11 count removed by exclusion |
| 3. Set | P12 approved by a person; P10 `yes`, `unresolved` or `no DOI`; rule 11 no excluded item under `blind` |
| 4. Collection | coverage: the map is of the uploads unless the set is in it |
| 5. Analysis | the strategy's shape; every assertion cites a Set row |
| 5. Analysis, scout table | P1 values from papers are claims, never a dataset, never pooled with measurements or fitted by a RUN; P2 units copied, converted only in a PLAN concordance |
| 6. Claims | P10 quote and location, DOI resolved online, verified or assumed; P12 approved before entering a PLAN |
| 7. Candidate Hypotheses | P11 NOT YET TESTED; P7 proposed thresholds; P10 `assumed only` candidates motivate a diagnostic batch, never a mechanism |
| 8. Attestation | P12 who approved what, when, and who confirmed the literature mode; rule 10 gate invocations, offline or online, and results |
