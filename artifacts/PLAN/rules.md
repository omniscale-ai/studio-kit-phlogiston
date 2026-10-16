# PLAN Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{plan_template}` — structural reference
- `{result_gate}` — gate for a final result; enforces the stopping rule of rule 7

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
   the run. If the run config provides a `literature_mode` field (`none`,
   `allowed` or `blind`), it is copied into section 2 as the Literature
   mode, shown at Approval and may be changed there; otherwise the agent
   proposes one and the human confirms it at Approval (P12). The mode is
   never assumed. Under `blind` the Excluded table is filled before
   approval.
7. **Budget is counted in batches.** One simulate call is one batch of a fixed
   number of experiments set by the apparatus; the total is shared across all
   phases and each phase type has its own hard call limit for every tool. The
   PLAN lists both, and a phase that reaches its limit analyses what it has
   instead of calling again. Unspent budget is not a saving: the run stops
   with a result only when the final COMPARISON has no `open` pair, selects
   a candidate, hands in the best available one with a reason why the
   remaining budget cannot change the selection, or the budget is spent, and
   only after `{result_gate}` PASS (COMPARISON rules 8-11). A failing
   criterion is not a stop condition, and spending the budget is not a route
   to a result: every batch is analysed before the next one is designed.
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
11. **A criterion changes only by revision, for a measurement reason.** The
    criteria are frozen when the first phase starts (P7). A threshold that
    turns out wrong is changed only in a new PLAN with a new ID, whose
    section 9 states the reason in terms of the measurement (the noise model,
    the sensitivity of the observable in some regime, what the pooled metric
    weights) and never in terms of which candidate it makes pass; it names
    the criterion, the old and new threshold, and the RUN evidence. The
    revision is recorded in section 11 with who approved it (in an autonomous
    run with pre-approved gates: `revision by the agent, <date>`, so a reader
    can see it). Every RUN on the final snapshot is re-judged under the new
    PLAN; verdicts under the old PLAN stand as written. A revision made after
    the candidates' verdicts are known is suspect by default: it is
    acceptable only if its reason would have been given before any RUN.
12. **Every threshold is attainable by a correct model before the first
    batch.** For each mechanical criterion with a threshold on data, section
    9 states its Attainability: what a correct candidate would score under the
    stated noise model, with the parameter uncertainty a fit to that noise
    leaves, computed or simulated (for example, the distribution of the pooled
    metric for the true structure fitted to noise-only replicates), and that
    the threshold admits it with margin. A pooled metric says how much a
    single unit in a highly sensitive regime can move it; if one unit can fail
    a correct model, the criterion is restated (per unit, robust, or weighted
    by the noise in that regime) before approval, not after.

## Where the principles land in a PLAN

| Section | Principles |
|---------|------------|
| 2. Prior Knowledge | P10 verified vs assumed, each literature claim citing its LITERATURE ID and Claims row; P12 literature mode and, under `blind`, the Excluded table set by the human |
| 3. Datasets | P1 origin per dataset; P2 units concordance |
| 4. Simulation Cost | P3 asked from a human, name and date |
| 6. Phase Sequence | P4 which phases may spend real experiments; P12 gates |
| 7. Experiment Design Policy | P5 justification types and design tool |
| 8. Hypothesis Space | P6 parameters added and applicability, selection rule declared here and executed in a COMPARISON; P8 pairwise, no composite score; P11 status register, updated only from a COMPARISON |
| 9. Verdict Criteria | P7 agreed, argued, frozen, attainable (rule 12), revised only by a new PLAN (rule 11); P9 how measured, listing order |
| 11. Approval | P3 and P7 confirmed explicitly; literature mode shown and confirmed at Approval; P12 |
