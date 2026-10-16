# RUN Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{run_template}` — structural reference
- `{result_gate}` — gate for a final result; reads the fields of rule 11 (COMPARISON rules, "Result gate")

---

1. **One RUN is one execution of one procedure on one dataset snapshot.** A
   fit, an estimation, a test, an optimisation, a classification: whatever the
   procedure, a simulate call is acquisition and belongs to the DATASET, a
   design-proposal call belongs to the phase output, and ranking against other
   candidates belongs to the COMPARISON. Two candidates are two RUNs, even when
   run in the same phase.
2. **Every RUN uses all experiments acquired so far.** Dropping one is a
   deviation with a reason stated in terms of the input (inert regime, errored
   batch), never in terms of how it came out.
3. **Quality is the PLAN's metric against its reference, never the raw
   objective against zero.** Compute the agreed quality metric exactly as the
   PLAN defines it and compare it with the reference the PLAN names (a noise
   floor, a held-out set, a reference solution). A score better than the
   reference allows is suspicious: overfitting or an unidentifiable candidate.
   A score worse than the threshold means something is missing. Report the
   metric next to the objective; the objective alone says nothing.
4. **An output that sits on a limit the procedure imposed is not a finding.** A
   parameter at its range bound, an optimum on an artificial constraint, a
   decision at the exact edge of its threshold: either widen the limit with a
   physical justification and rerun, or record the output as undetermined. If
   the PLAN declares a criterion for it, it fails as imprecise.
5. **Units that carry no information about the question are not support.** For
   every experiment in the snapshot say which outputs it actually constrains.
   An experiment in an inert regime, or outside the procedure's sensitivity,
   informs only what it can; counting it as support for the main outputs is the
   error.
6. **Every structural choice baked into the candidate is an assumption with a
   licence.** A functional form, a distribution family, a linearity, a kernel,
   a reference point: name the diagnostic batch that distinguishes the choice
   from its alternatives, or mark it `borrowed: <source>` and say so in the
   verdict notes.
7. **The verdict table has exactly the PLAN's rows.** A concern that surfaces
   during the RUN goes into Deviations or into the next PLAN, never into a new
   verdict row. Thresholds per P7.
8. **Every fail names its mode.** Biased: systematic departure at some
   condition, a term or mechanism missing or wrong. Imprecise: no systematic
   departure, but an output poorly determined (on a limit, wide spread,
   correlated with another). A fail without a mode is not a verdict. The
   Failure mode cell says where: `biased: <units or regime>` or
   `imprecise: <output>`; the result gate reads the mode word first.
9. **Reproduction is the request payload.** Store the exact tool JSON. If the
   simulator is unseeded, the stored measurements, not a fresh simulation, are
   the reference; re-running the procedure on stored data must reproduce the
   outputs.
10. **A RUN ends with the input to the next design, about itself only.**
    Outputs state which hypothesis IDs this RUN supports or falsifies, which
    outputs remain poorly determined, and which condition ranges are untested.
    Which pair of candidates is indistinguishable, and what would separate
    them, is the COMPARISON's question; a RUN does not rank itself against
    others. The next batch's justification must point at one of these, at an
    open pair of the COMPARISON, or, when the COMPARISON selects nothing, at a
    fail mode of a non-dominated candidate (COMPARISON rule 10); a batch that
    none of them motivated is unjustified by definition. A batch is run to be
    analysed: the RUN on the snapshot that includes it is written before the
    next batch. `{design_log} hook --require-analysis` enforces this before
    every call and `{result_gate} --require-analysis` (R7) checks it at the
    end.
11. **Snapshot, structure and candidate file are fields the result gate
    reads.** Section 1 carries `**Dataset**:` (the DATASET ID) and
    `**Experiments**:` (every experiment of the snapshot by name, `e1–e12` for
    a numeric range), identical to those of the COMPARISON the RUN is a
    candidate in. Section 3 carries `**Structure**:`, the candidate's
    structural family: the functional form, mechanism or model class,
    independent of parameter values, ranges, initial values and settings. Two
    RUNs that differ only in those share a Structure; a candidate that adds,
    removes or replaces a term has its own. Section 3 also carries
    `**Candidate file**:` and `**Candidate sha256**:`, the file this candidate
    would be submitted as and the sha256 of its bytes; when the file changes,
    the RUN is redone or the hash updated with a Deviation saying why. The
    submitted file is byte-identical to the selected RUN's candidate file.
12. **A pooled criterion that fails is diagnosed before it is believed.**
    When a criterion pooled over units (an RMS, a likelihood, a count over all
    experiments) fails, Outputs give the per-unit breakdown: each unit's
    contribution next to its condition. If the failure is concentrated in a
    few units, the RUN examines them and names why before it calls the
    candidate biased: a regime where the observable is very sensitive to small
    parameter or condition errors, an inert or extreme regime that informs
    little (rule 5), noise, or a missing term or mechanism (rule 8). The
    verdict row keeps the PLAN's threshold and its result; the diagnosis goes
    into Outputs and the Failure mode cell (`biased: e7, e9 in the steep
    regime`), and it is what the next batch targets. A threshold is never
    loosened inside a RUN or after seeing which candidate it favours; a
    criterion that turns out to measure the wrong thing is a PLAN revision
    (PLAN rule 11).

## Where the principles land in a RUN

| Section | Principles |
|---------|------------|
| 1. Unit | P1 origin counts; a simulated-data RUN is not a result about the real system |
| 3. Candidate Spec | P8 Structure, so that alternatives are structurally different; P6 free-parameter count, nested simpler candidate, claimed applicability vs explored range |
| 5. Assumptions | P2 first row cites the concordance; P10 ranges or priors verified or assumed |
| 7. Outputs | P7 per-unit breakdown of a failing pooled criterion (rule 12); P6 parsimony check; P11 supported / falsified by hypothesis ID in the handoff (P8 pairwise standing lives in the COMPARISON) |
| 8. Deviations | P7 doubts about a criterion with a proposal for a new PLAN; P12 rejection feedback verbatim |
| 9. Verdict | P7 exactly the PLAN's rows and thresholds; P9 Measured by, order, judged rows not filled by the agent |
