# DATASET Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{dataset_template}` — structural reference

---

1. **Every condition axis is declared MEASUREMENT or SYNTHESIS.** A synthesis
   axis varies the sample; a measurement axis varies the measurement of one
   sample. Fitting a rate law across a synthesis axis produces a number with
   the right units and no meaning. Enforced by `graph_gate.py` G5.
2. **The trusted instrument range is stated, not assumed.** Give the signal
   level at both extremes of the sweep. Where signal approaches the noise
   floor, the data there is not noisy data — it is not data.
3. **Geometry is per sample, or declared missing.** If samples differ in the
   geometry that converts measurement to material property, that geometry
   varies with whatever axis it correlates with, and any trend along that axis
   is confounded until it is divided out.
4. **Instrument metadata is checked, not copied.** Sentinel values from
   disconnected sensors (implausible temperatures, zeroed channels) must be
   identified here rather than propagated into analysis as fact.
5. **Format traps are recorded.** Decimal commas, unusual encodings and
   silently-truncating parsers belong here; the next person will hit them too.
6. **The acquisition order is stated.** Which way the independent variable was
   traversed, and whether once or both ways. A both-ways acquisition is two
   measurements: declare `direction` as a MEASUREMENT axis, fit each, and
   report their disagreement. Keeping one branch and dropping the other is a
   selection the protocol was designed to prevent. Enforced by
   `graph_gate.py` G10.

## How these read in a simulator-backed agent run

- **Axis kinds.** The axis the simulator returns a trajectory along (time, for
  a dynamics simulator) is the MEASUREMENT axis: a model is fitted along it
  inside one experiment. Every entry of the condition vector is a SYNTHESIS
  axis: one value per experiment, varied by the design. Fitting one law across
  experiments without the SYNTHESIS axes in the model is the error rule 1
  forbids.
- **Trusted range.** The observable window and sampling are fixed by the
  simulator contract; there may be no point at the origin. σ comes from the
  simulator config. A change smaller than about 2σ over the window is not
  information about the dynamics. Where a condition drives the system into an
  inert regime (for enzymes: above the denaturation temperature) the trajectory
  is flat and informs only the parameters of that regime.
- **Geometry per sample is the condition conversion here.** Conditions may be
  proposed in one unit and applied in another (the enzyme device takes volumes
  in mL, normalises them to the reactor and converts to mM). Record the
  conversion factor per experiment, or any trend along a condition axis is
  confounded with it.
- **Instrument metadata.** A tool failure fails the phase. A batch that errored
  is absent, never partial data. Say which batch and why.
- **Format traps.** Keys can differ between tool JSON and model-spec expressions
  (enzyme device: `temperature` vs `T`). Units of proposed conditions can differ
  from units of effective conditions. Returned measurement-axis values can be
  shifted by a start offset.
- **Acquisition order.** Batches are ordered by phase (PRE-1, DIAG, CYCLE-2 …).
  The justification of every batch is written in the agent's planning step
  before the call; copy it, do not reconstruct it from the result.

## Where the principles land in a DATASET

| Section | Principles |
|---------|------------|
| 1. Origin and Source | P1 first line: ground-truth / simulator / mixed |
| 4. Units of Measure | P2 every quantity, its unit, its source |
| 5. Axes | P6 Explored range next to Allowed range |
| 6. Acquisition | P1 Origin per batch; P5 Justification and Design method; P4 Simulator preview; P3 Actual duration; P12 Approved by |
| 8. Known Defects | P3 departures from the confirmed cost |
