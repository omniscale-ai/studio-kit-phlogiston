# RUN Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{run_template}` — structural reference

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
   correlated with another). A fail without a mode is not a verdict.
9. **Reproduction is the request payload.** Store the exact tool JSON. If the
   simulator is unseeded, the stored measurements, not a fresh simulation, are
   the reference; re-running the procedure on stored data must reproduce the
   outputs.
10. **A RUN ends with the input to the next design, about itself only.**
    Outputs state which hypothesis IDs this RUN supports or falsifies, which
    outputs remain poorly determined, and which condition ranges are untested.
    Which pair of candidates is indistinguishable, and what would separate
    them, is the COMPARISON's question; a RUN does not rank itself against
    others. The next batch's justification must point at one of these or at an
    open pair of the COMPARISON; a batch that none of them motivated is
    unjustified by definition.

## Where the principles land in a RUN

| Section | Principles |
|---------|------------|
| 1. Unit | P1 origin counts; a simulated-data RUN is not a result about the real system |
| 3. Candidate Spec | P6 free-parameter count, nested simpler candidate, claimed applicability vs explored range |
| 5. Assumptions | P2 first row cites the concordance; P10 ranges or priors verified or assumed |
| 7. Outputs | P6 parsimony check; P11 supported / falsified by hypothesis ID in the handoff (P8 pairwise standing lives in the COMPARISON) |
| 8. Deviations | P7 doubts about a criterion with a proposal for a new PLAN; P12 rejection feedback verbatim |
| 9. Verdict | P7 exactly the PLAN's rows and thresholds; P9 Measured by, order, judged rows not filled by the agent |
