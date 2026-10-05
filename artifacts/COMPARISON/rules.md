# COMPARISON Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{comparison_template}` — structural reference

---

1. **One COMPARISON per snapshot per phase.** Candidates run on different snapshots are not comparable and do not appear in the same COMPARISON. The
   snapshot is named by DATASET ID and experiment list, and every listed RUN
   names it as its Unit.
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
   is not forced to have a winner.
5. **Open pairs are the only source of discrimination targets.** A
   non-dominated pair the snapshot cannot separate is written with the
   hypotheses that differ between its members and the condition that would
   separate them. The next batch's `information →` justification must name an
   open pair from the latest COMPARISON; a discrimination batch without one is
   unjustified.
6. **Status updates flow to the PLAN by ID.** Section 7 is the only place a
   hypothesis moves from NOT YET TESTED to SUPPORTED or FALSIFIED, and each
   move names the RUN and batch. A COMPARISON never edits criteria, thresholds,
   or the selection rule.
7. **A COMPARISON is a decision record.** It is approved by a person and a
   date, and a rejected one is redone with the feedback text kept verbatim.

## Where the principles land in a COMPARISON

| Section | Principles |
|---------|------------|
| 1. Snapshot | P1 origin composition of the snapshot |
| 3. Criterion Vectors | P7 exactly the PLAN's criteria; P9 `not evaluated` rows excluded from selection |
| 4. Pairwise Dominance | P8 pairwise, no composite score |
| 5. Selection | P6 tie threshold then fewer parameters; P8 a ranking never replaces a batch |
| 6. Open Pairs | P5 the `information →` targets of the next batch |
| 7. Hypothesis Status Updates | P11 statuses by ID with evidence |
| 8. Approval | P12 person, date, feedback verbatim |
