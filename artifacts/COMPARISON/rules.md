# COMPARISON Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{comparison_template}` — structural reference
- `{result_gate}` — gate for a final result ("Result gate" below)

---

1. **One COMPARISON per snapshot per phase.** Candidates run on different snapshots are not comparable and do not appear in the same COMPARISON. The
   snapshot is named by DATASET ID and experiment list, and every listed RUN
   names it as its Unit. Section 1 carries the snapshot as `**Dataset**:` and
   `**Experiments**:` lines, identical to each candidate RUN's (RUN rule 11).
   A later COMPARISON on the same snapshot that replaces an earlier one names
   it in `**Supersedes**:`.
2. **Vectors are copied, not recomputed.** Each row of section 3 is the RUN's
   own Verdict, in the PLAN's order. A COMPARISON that disagrees with a RUN's
   verdict is wrong, not the RUN. A candidate with a `not evaluated` row is
   listed, so the record shows it existed, and is excluded from selection.
3. **Dominance is literal.** A dominates B when A wins or ties every criterion
   and wins at least one. No weighting, no score, no "mostly better".
   Dominated candidates are dropped and the table says which pair dropped them.
4. **Selection follows the PLAN rule word for word.** Among non-dominated
   candidates, quality within the tie threshold goes to fewer free parameters. The
   selection cites the rule line that decided it. If no candidate passes every
   mechanical gate, nothing is selected and the COMPARISON says so; a selection
   is not forced to have a winner. Section 5 states it as `**Selected**:` with
   the RUN ID, or `none`.
5. **Open pairs are the only source of discrimination targets.** A
   non-dominated pair the snapshot cannot separate is written with the
   hypotheses that differ between its members and the condition that would
   separate them. The next batch's `information →` justification must name an
   open pair from the latest COMPARISON; a discrimination batch without one is
   unjustified. Every candidate the selected one does not dominate forms a
   pair with it. Each pair has a Status: `open`; `closed by batch <id>` once a
   batch whose `information →` justification names the pair is in the
   snapshot; or `unresolvable: <reason>`, where the reason says why the
   remaining budget cannot separate the pair (the separating condition lies
   outside the allowed ranges, or the predicted difference stays below the
   noise at every allowed condition the remaining batches can reach).
6. **Status updates flow to the PLAN by ID.** Section 7 is the only place a
   hypothesis moves from NOT YET TESTED to SUPPORTED or FALSIFIED, and each
   move names the RUN and batch. A COMPARISON never edits criteria, thresholds,
   or the selection rule.
7. **A COMPARISON is a decision record.** It is approved by a person and a
   date, and a rejected one is redone with the feedback text kept verbatim.
8. **Stop only when nothing separable is left.** While a pair is `open` and
   budget remains, the next step is the batch that separates it, then new
   RUNs and a new COMPARISON on the larger snapshot, not a final result.
   Fewer experiments, saving budget or efficiency is never a reason to stop
   while an open pair is separable within the budget. One candidate is not a
   selection: a final result needs at least two candidates of different
   Structure on the final snapshot.
9. **A final result is presented only after `{result_gate}` PASS.** The
   submitted file is the selected RUN's candidate file, byte for byte. A
   result the gate refuses is not presented; fix what it names (usually: run
   the separating batch, write the missing RUN, redo the COMPARISON on the
   final snapshot) and run the gate again.

## Result gate (`{result_gate}`)

Run before presenting a final result, next to `cfs validate` and the design
gate:

`python3 {result_gate} --plan architecture/PLAN.md --dataset architecture/DATASET.md --runs architecture/runs --comparisons architecture/comparisons --submission <file> [--source <acquisitions>] --budget-left <batches left>`

Exit 0 PASS, 1 FAIL, 2 usage error or unreadable `--source` / `--submission`.
One line per violation `[Rk] message`, `note:` lines, then PASS or FAIL.
`--source` is the same non-agent acquisitions record as for the design gate;
without it the experiments are read from DATASET section 6 (Experiments
column). Without `--budget-left` an `open` pair fails, since the gate cannot
tell whether budget remains.

| ID | The gate refuses the result unless |
|----|------------------------------------|
| R1 | exactly one COMPARISON, not superseded, is on the final snapshot: its `**Dataset**:` is the DATASET ID and its `**Experiments**:` are exactly the experiments acquired; one on an older snapshot does not count (rule 1) |
| R2 | it lists at least two candidates; every one has a RUN file on the same snapshot; every RUN on that snapshot is listed; at least two have different `**Structure**:` and different Candidate Specs (rule 8, RUN rule 11) |
| R3 | section 3 columns are the PLAN's criterion IDs in order, each RUN's Verdict has exactly those rows, and every cell equals the RUN's result (rule 2) |
| R4 | `**Selected**:` names a candidate that passes every mechanical row, has no `not evaluated` row, is dominated by no candidate, and whose `**Candidate sha256**:` equals the sha256 of the submitted file (rules 2, 3, 4, 9) |
| R5 | section 6 has a Status for every pair; every candidate the selected one does not dominate is paired with it; `closed by batch <id>` names a DATASET batch with an `information →` justification; `unresolvable:` gives a reason that is not about using fewer experiments; and no pair is `open` while budget remains (rules 5, 8) |
| R6 | every RUN and COMPARISON passes the structural checks of `cfs validate` (headings, numbering, `**ID**:`, unique IDs), replicated from `constraints.toml` |

Dominance in R4 and R5 is rule 3 on the pass / fail vectors; a candidate with
a `not evaluated` row is neither selectable nor a rival.

**Preventing the submission (integration point).** The kit does not own the
submission interface; it ships the check, and the harness wires it in, as for
the design log hook. Right before accepting a final result the trusted party
(oracle or harness, running the repository's copy of the kit, never the
agent's) runs `{result_gate} hook --witness <result_witness.jsonl> <the same
options>`. The hook appends one JSON line (time, gate version and sha256,
verdict PASS / FAIL / ERROR, violations, notes, submission path and sha256,
COMPARISON and selected RUN, budget left, source and its sha256) and exits 0
to accept, 2 to refuse (report on stderr), 1 on a usage error. The witness is
written by the hook only; the agent never edits it.

## Where the principles land in a COMPARISON

| Section | Principles |
|---------|------------|
| 1. Snapshot | P1 origin composition of the snapshot |
| 3. Criterion Vectors | P7 exactly the PLAN's criteria; P9 `not evaluated` rows excluded from selection |
| 4. Pairwise Dominance | P8 pairwise, no composite score |
| 5. Selection | P6 tie threshold then fewer parameters; P8 a ranking never replaces a batch; `**Selected**:` checked against the submission by `{result_gate}` |
| 6. Open Pairs | P5 the `information →` targets of the next batch; P8 Status, and no final result while a pair is open and budget remains |
| 7. Hypothesis Status Updates | P11 statuses by ID with evidence |
| 8. Approval | P12 person, date, feedback verbatim |
