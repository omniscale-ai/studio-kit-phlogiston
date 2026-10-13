# LITERATURE Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{literature_template}` — structural reference
- `{literature_workflow}` — the four strategies; a LITERATURE is produced only by running one
- `{plan_template}` — section 2 of the PLAN: the literature mode and the Excluded table

---

1. **One LITERATURE is one request along one strategy.** `related`,
   `review`, `metareview` or `scout`, named in section 1. A request that
   needs two strategies is two artifacts. A search that followed no strategy
   is not recorded as a LITERATURE.
2. **The Set is the universe.** Section 3 lists every paper the analysis may
   cite; a paper outside it is not mentioned. Every assertion about a paper
   cites its Set row. The request's anchor is named without a row number;
   every other paper is cited by Set row. The Set is approved by a person
   before analysis starts (P12), and the approval is recorded with name and
   date.
3. **A DOI that does not resolve is not a reference.** Section 3 marks each
   row's `resolved` cell `yes`, `unresolved` or `no DOI` (DOI cell `—`).
   With `--resolve` the gate fails a row whose DOI does not resolve unless
   its cell says `unresolved`; a row marked `unresolved` or `no DOI` does not
   block `verified`, but every Claims row citing it must be `assumed` (the
   gate fails a `verified` claim on such a row). Nothing is removed
   silently (L3, L4).
4. **A claim is a quote with a location.** Section 6 carries the paper's
   words and where they were found on this run. Without both, the status is
   `assumed`, and an assumed claim licenses no range and no mechanism (P10).
   Claims row n is the n-th data row of the Claims table, counted from 1 in
   table order; rows are never reordered or deleted after a PLAN cites them.
   Citations read `<LITERATURE ID>, claim n`.
5. **Sources are stated, including the ones that did not run.** Section 2
   names each source as ran, skipped with reason, or not configured, with
   the query that can be rerun. A source substituted for another is a
   deviation and is written as one.
6. **A collection is not the subject.** When Hypothesis ran, section 4
   states how many of the approved set its collection holds. Below half,
   the artifact cannot become `verified`: the claims map describes the
   uploads, not the field.
7. **No value without a passage; a value from a paper stays a claim.** In
   `scout`, a row carries a value only with the passage it came from (L10);
   units are copied as printed and converted only in a PLAN concordance
   (P2). The scout table stays in section 5 of the LITERATURE, with the same
   rows as CSV beside it. A value reaches a PLAN only as a `verified` claim
   cited in the PLAN's section 2 (P10), where it may license a parameter
   range or motivate a hypothesis. It never becomes a DATASET: there is no
   `literature` origin, a RUN never fits it, and it is never pooled with
   measurements (P1).
8. **Analysis is written over the Set and in the strategy's shape.** Path 2
   writes groups by named authors with an assessment and its evidence;
   Path 3 writes trends from reviews and makes no primary-source claim;
   Path 4 writes one row per measurement. The shape is not negotiable per
   run; it is what makes the four outputs comparable across runs.
9. **Hypotheses are proposed here, confirmed in the PLAN.** Section 7 rows
   are candidates with a proposed diagnostic condition and status NOT YET
   TESTED. Thresholds found in the literature are `proposed` (P7). Section 1
   records the PLAN the request serves and the literature mode it ran under,
   copied from that PLAN. The PLAN cites the LITERATURE id; the LITERATURE
   never cites a PLAN's results.
10. **`verified` is earned by the gate online, against the PLAN.**
    `scripts/lit_gate.py` runs its structural checks on every invocation;
    `--resolve` also looks up every DOI in OpenAlex; `--plan <PLAN.md>`
    reads the PLAN's Literature mode and Excluded table (rule 11). A
    LITERATURE becomes `verified` only after a PASS of an online invocation
    that has both `--resolve` and `--plan` (L9). An offline run without
    `--plan` is a structural check only: it leaves the status `draft` and
    never clears blind compliance. The Attestation records each invocation
    exactly as run, in the template's line form, with its result and date.
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
    does not see them). Matching is case-insensitive throughout: a `doi`
    item matches a DOI exactly, after any `https://doi.org/` prefix is
    stripped from both; a `title`, `term`, `benchmark` or `author` item
    matches as a substring. Offline the gate compares `doi` items with the
    DOI cell and the other types with the DOI, title and OA link cells of
    every Set row, with Analysis and Claims, and with the Request and the
    Sources query column (a query that contains an excluded item means it
    was retrieved). Venue and authors are not Set columns and are compared
    only with `--resolve`, against the OpenAlex record of each row that has
    a DOI. An offline PASS under `blind` therefore does not clear `author`
    items; only the online PASS with `--plan` does. An anchor that matches
    an excluded item is refused at intake. A matched paper is removed from
    the Set before approval, and section 2 gives the number removed, never
    the matched text; Analysis never names it. With `--plan` the gate fails
    if the PLAN's mode is `none`, if the Request's `PLAN:` ID differs from
    the PLAN's ID, if the Request's Literature mode differs from the PLAN's,
    and, under `blind`, on any excluded hit or if `Exclusions checked`
    differs from the PLAN's Excluded row count (L11). Without `--plan` L11
    passes only when the Request's Literature mode is exactly `allowed`;
    `blind` and any other value fail. `scripts/lit_run.py` refuses (exit 2,
    before any request) to overwrite an existing artifact or CSV unless
    `--force` is given. The PLAN's `LITERATURE
    drawn on` line is not checked by the gate; keeping it complete is the
    PLAN author's duty at Approval.

## Gate rules (`scripts/lit_gate.py`)

`python3 scripts/lit_gate.py <file>.md [--plan <PLAN.md>] [--resolve]`;
exit 0 PASS, 1 FAIL, 2 usage. Every invocation runs all checks it can;
`--resolve` adds the OpenAlex lookups, `--plan` the PLAN checks.

| ID | The gate fails the artifact unless |
|----|------------------------------------|
| L1 | section 1 names exactly one of the four strategies (rule 1) |
| L2 | the Set is approved by a person with a date (rule 2) |
| L3 | every Set row has a DOI or the DOI cell `—` with `no DOI`; every `resolved` cell is `yes`, `unresolved` or `no DOI`; with `--resolve`, every DOI looked up resolves unless its cell says `unresolved` (rule 3) |
| L4 | every `verified` claim has a quote and a location and cites a Set row whose `resolved` cell is `yes`; any other claim is `assumed` (rules 3, 4) |
| L5 | Analysis cites only existing Set rows; the anchor is exempt (rule 2) |
| L6 | every Candidate Hypotheses row cites Claims rows, or the section says `none` (rule 9) |
| L7 | Collection says `not used`, or gives `k of N` with k/N ≥ 0.5 (rule 6) |
| L8 | every source marked `ran: yes` records its query (rule 5) |
| L9 | status `verified` only if L1–L8, L10 and L11 pass and the Attestation records an `online` PASS whose invocation has `--resolve` and `--plan`; an offline run on a `verified` file fails L9 when no such Attestation line exists (rule 10) |
| L10 | under `scout`, every CSV value carries its passage (rule 7) |
| L11 | with `--plan`: the PLAN's mode is not `none`, the Request's `PLAN:` ID and Literature mode equal the PLAN's, and under `blind` there is no excluded hit and `Exclusions checked` equals the PLAN's Excluded row count; without `--plan`: the Request's Literature mode is exactly `allowed` (rule 11) |

## Where the principles land in a LITERATURE

| Section | Principles |
|---------|------------|
| 1. Request | P12 literature mode set by a person in the PLAN and copied here; rule 11 exclusions checked under `blind`, compared with the PLAN by the gate; P3 cost stated before running and cost used, retrieval and gate lookups together |
| 2. Sources | P3 budget used per source; honesty about what ran; rule 11 count removed by exclusion |
| 3. Set | P12 approved by a person; P10 `yes`, `unresolved` or `no DOI`; rule 11 no excluded item under `blind` |
| 4. Collection | coverage: the map is of the uploads unless the set is in it |
| 5. Analysis | the strategy's shape; every assertion cites a Set row |
| 5. Analysis, scout table | P1 values from papers are claims, never a dataset, never pooled with measurements or fitted by a RUN; P2 units copied, converted only in a PLAN concordance |
| 6. Claims | P10 quote and location, DOI resolved online, verified or assumed; P12 approved before entering a PLAN |
| 7. Candidate Hypotheses | P11 NOT YET TESTED; P7 proposed thresholds |
| 8. Attestation | P12 who approved what, when; rule 10 gate invocations, offline or online, and results |
