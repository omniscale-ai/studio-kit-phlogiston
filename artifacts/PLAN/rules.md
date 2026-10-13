# PLAN Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{plan_template}` — structural reference

---

1. **The plan gates the work.** Analysis workflows check for an approved plan
   before heavy or irreversible steps.
2. **Name the quantity that answers the question.** If none does, stop and say
   so; that is a more valuable output than a number that does not mean what the
   question asked.
3. **Changing a calibrated constant is ask-first.** Recalibrating because a
   result looks wrong is legitimate only when the recalibration is scored
   against ground truth and recorded as a new CALIBRATION.
4. **Approval is a person and a date.**
5. **The plan declares what a verdict must answer.**

## In a simulator-backed agent run

6. **One run is one PLAN, written before the first phase executes.** The run's
   `research_question`, `literature`, `experiment_budget` and `num_cycles` are
   copied into it, not paraphrased; `literature` is the materials attached to
   the run. The run's `literature_mode` (`none`, `allowed` or `blind`) is
   copied into section 2 as the Literature mode. When the run has no
   `literature_mode` field, the agent proposes one and the human confirms it
   at Approval (P12); a mode copied from the run is shown at Approval and may
   be changed there. The mode is never assumed. Under `blind` the Excluded
   table is filled before approval.
7. **Budget is counted in batches.** One simulate call is one batch of a fixed
   number of experiments set by the apparatus; the total is shared across all
   phases and each phase type has its own hard call limit for every tool. The
   PLAN lists both, and a phase that reaches its limit analyses what it has
   instead of calling again.
8. **The phase sequence is the skeleton.** PRE-1, then per cycle Model
   Refinement and Design of Experiments with Mechanism Discrimination inserted
   after the first cycle, then Final Model Formulation and Report. Gates and
   feedback per P12.
9. **The falsification checklist is declared up front.** Every competing
   mechanism or effect in the Hypothesis Space starts as NOT YET TESTED. DIAG
   exists to test them; one is accepted only when adding it to the model
   reduces loss on a batch designed to reveal it. Status vocabulary per P11.
10. **Verdict criteria are computable from what the run produces.** The
    quality metric and every other mechanical criterion is a function of the
    fit tool's outputs, the DATASET and the PLAN itself. A criterion that
    nothing in the run can compute and no named human judges does not belong
    in the table.

## Where the principles land in a PLAN

| Section | Principles |
|---------|------------|
| 2. Prior Knowledge | P10 verified vs assumed, each literature claim citing its LITERATURE ID and Claims row; P12 literature mode and, under `blind`, the Excluded table set by the human |
| 3. Datasets | P1 origin per dataset; P2 units concordance |
| 4. Simulation Cost | P3 asked from a human, name and date |
| 6. Phase Sequence | P4 which phases may spend real experiments; P12 gates |
| 7. Experiment Design Policy | P5 justification types and design tool |
| 8. Hypothesis Space | P6 parameters added and applicability, selection rule declared here and executed in a COMPARISON; P8 pairwise, no composite score; P11 status register, updated only from a COMPARISON |
| 9. Verdict Criteria | P7 agreed, argued, frozen; P9 how measured, listing order |
| 11. Approval | P3 and P7 confirmed explicitly; literature mode shown and confirmed at Approval; P12 |
