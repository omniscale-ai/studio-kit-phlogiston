# Principles

Cross-cutting invariants for every artifact in this kit (PLAN, DATASET, RUN,
COMPARISON). Each `rules.md` loads this file first and keeps only what is
specific to its own kind. A principle is
stated once here; the per-kind line says where it lands in that artifact.

P1. **Every dataset declares its origin.** Ground truth (real measurements) or
    simulator. A simulated dataset is evidence about the model and the design,
    never about the real system, and a result obtained on it is reported as
    such. Results from the two origins are never pooled or averaged as if they
    were one instrument.
    PLAN: Datasets table, Origin column. DATASET: first line of Origin and
    Source; Origin column per batch. RUN: origin counts in Unit; a simulated-data RUN is never reported as a result about the real system.

P2. **Units are reconciled before the first RUN.** One concordance table: each
    quantity, its unit in the model and in every dataset. A mismatch or an
    unknown unit blocks approval. A conversion is written with its factor,
    never applied silently in code or prose; "assume the usual unit" is the
    error.
    PLAN: Datasets, concordance table; criterion `units-match`. DATASET: Units
    of Measure table with the source of every unit. RUN: first assumption row
    cites the concordance; a RUN whose inputs disagree in units with the candidate spec is invalid whatever its score and fails `units-match` as biased.

P3. **Simulation time and cost are asked from a human, not assumed.** Before
    approval a human states how long one experiment and one batch take and what
    they cost in compute, and the same for a real experiment if a ground-truth
    apparatus exists. Recorded with name and date. An agent that cannot find the
    answer asks instead of estimating.
    PLAN: Simulation Cost table; empty table means not approvable. DATASET:
    Actual duration per batch against the confirmed figure; a material
    departure goes into Known Defects and is raised with the human before the
    next batch.

P4. **Preview on the simulator before spending real experiments.** When a new
    experiment is proposed for a ground-truth apparatus and a simulator exists,
    the proposed conditions are run on the simulator first. Skipping the
    preview is a deviation with a stated reason.
    PLAN: Phase Sequence says which phases may spend real experiments.
    DATASET: Simulator preview column names the preview batch or RUN, or says
    why there was none; the preview is what licenses spending a real
    experiment.

P5. **New points are designed, not guessed.** Every proposed experiment is
    justified before it runs as exactly one of: variance reduction (which
    parameter it tightens), information or discrimination (which hypotheses
    predict different observables there), or boundary of applicability (which
    assumption or range it pushes). Use the design tool the agent has, with the
    current model and estimates, whenever it applies; a manual design states
    why the tool was not used. A point that duplicates an existing condition
    within noise, or has no justification, is not run. "Explore" is not a
    justification.
    PLAN: Experiment Design Policy. DATASET: Justification and Design method
    columns per batch, written before the call. RUN: Outputs end with the
    handoff (variance and boundary targets). COMPARISON: Open Pairs are the
    only `information →` targets.

P6. **A hypothesis is the fewest free parameters that explain, plus where it holds; equal quality goes to the fewer parameters.** The starting candidate is the simplest one; every further hypothesis states how many free parameters it adds and the conditions under which it is claimed to apply. The PLAN
    declares what "equal quality" means before any RUN; among candidates within
    that threshold on the same snapshot the one with fewer parameters is
    selected, and a parameter stays only if removing it breaks equality. Better
    loss alone never justifies an extra parameter. Applicability is claimed
    only where it was tested: a claim beyond the explored condition ranges is
    an extrapolation, not a result.
    PLAN: Hypothesis Space fields Parameters added and Applicability;
    selection rule; criteria `parsimony` and `applicability`. DATASET: Explored
    range next to Allowed range per SYNTHESIS axis. RUN: names the nested simpler candidate and the quality difference; within the tie threshold the simpler candidate is selected and the extra parameter fails `parsimony` as
    imprecise; a claim beyond the explored range fails `applicability` as
    biased. COMPARISON: Selection executes the rule across all candidates on
    one snapshot.

P7. **The metric is agreed with a human, argued when proposed, and frozen
    while the work runs.** The agent asks what quantity is judged and at what
    threshold. A criterion the agent proposes says what it measures, why it
    answers the research question, and what it would miss. A row without a
    human's name and date is a proposal, not a criterion. The criteria table is
    frozen when the first phase starts: no row added, removed, or
    re-thresholded. A criterion that turns out wrong is raised with the human;
    the fix is a new PLAN with a new ID, and verdicts under the old PLAN stand.
    PLAN: Verdict Criteria blocks, Origin and justification and Confirmed by fields, Frozen at line. RUN: the verdict table has exactly the PLAN's rows and
    thresholds; a doubt about a criterion goes into Deviations with a proposal
    for a new PLAN, never into a re-scored, rounded, or reinterpreted row.

P8. **Candidates are compared pairwise, the verdict is a vector, and a
    ranking never replaces an experiment.** With more than two candidates there
    is no single score: each pair is compared criterion by criterion on the
    same snapshot, dominated candidates are dropped, and the non-dominated
    pairs are exactly what the next discrimination batch must separate.
    Criteria are never weighted into one number; a candidate that passes more
    rows is better on those rows, not "better". A ranking used instead of the
    discriminating batch is the antipattern this principle exists to stop.
    PLAN: selection rule declared in Hypothesis Space. COMPARISON: Criterion
    Vectors, Pairwise Dominance, Selection, Open Pairs; one per snapshot per
    phase. RUN: reports only its own vector and never ranks itself.

P9. **Every criterion says how it is measured; cheap gates run first; the agent does not judge its own result.** A criterion is `mechanical` with its
    formula or test, or `judged by` a named human, or a judge with a
    CALIBRATION reference that ships with the kit; a judged criterion with
    neither fails closed. Rows are evaluated in the PLAN's order, mechanical
    before judged; the first failing mechanical row stops the pass, rows below
    it are `not evaluated`, and the artifact goes back to the agent, not
    forward to review or to a human. Judged rows are filled by the named human
    or calibrated judge; the agent proposes evidence for them and does not
    write pass or fail.
    PLAN: How measured field; listing order. RUN: Measured by column; evaluation
    order in Verdict.

P10. **A claim is verified before it licenses anything.** Literature and
    recalled memory enter the Hypothesis Space or a parameter range only with a
    quote and its location in the source, checked on this run. An unverifiable
    claim is `assumed`: it may motivate a diagnostic batch, never a range or a
    mechanism.
    PLAN: Prior Knowledge marks `verified` / `assumed`. RUN: Parameter ranges
    row in Assumptions is `verified` or `assumed`, and an assumed range is
    reported as such in the verdict notes.

P11. **Falsified stays falsified.** Hypothesis status is NOT YET TESTED,
    SUPPORTED or FALSIFIED, each with the batch and RUN that set it. A
    FALSIFIED hypothesis is not re-proposed, in the same or a renamed form,
    without new data the falsifying batch did not contain.
    PLAN: Hypothesis ID, Status field and vocabulary in Hypothesis Space; the register. COMPARISON: Hypothesis Status Updates; the only place a status
    changes, with RUN and batch as evidence. RUN: handoff names the hypothesis IDs this RUN supports or falsifies.

P12. **Human gates and their feedback are part of the record.** Every phase
    ends at a human approval gate. A rejected phase re-runs with the feedback
    text in context, and that text is kept verbatim on the artifacts it
    changed, with what changed because of it.
    PLAN: Phase Sequence; Approval. DATASET: Approved by per batch. RUN:
    Deviations cite the feedback verbatim. COMPARISON: Approval of the
    selection.
