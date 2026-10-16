# DATASET Rules

**Dependencies**:
- `{principles}` — cross-cutting invariants P1–P12; load before these rules
- `{dataset_template}` — structural reference
- `{design_log}`, `{design_gate}` — pre-registration log and its gate (P5)

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
  The justification of every batch is written to the design log before the
  call (next section); copy it, do not reconstruct it from the result.

## Pre-registration log (P5)

The design log `architecture/design_log.jsonl` is the only source of the
Justification and Design method columns of section 6. It is checked by
`{design_gate}`; `cfs validate` checks structure only and cannot see order in
time.

1. **Before every batch, append one entry; then call.** Use
   `python3 {design_log} append --log architecture/design_log.jsonl --batch <id>
   --phase <phase> --points <json> [--justification '<type> → <target>']
   --design-method '<tool, criterion, seed>' | 'manual: <reason>'`.
   The entry holds every point (a name and the condition vector, exactly as it
   will be passed to the call) with exactly one `type → target` justification,
   type `variance`, `information` or `boundary` (P5), and the batch's design
   method. `--points` is `{"<name>": {"conditions": {…}, "justification":
   "<type> → <target>"}, …}`; `--justification` is the default for points that
   give none (`{"<name>": {<conditions>}}`). A target is one line with no
   backtick, and a `|` in a target or in the design method is written `\|`:
   section 6 copies them verbatim into a table cell, the target inside
   backticks. A `;` in a target is allowed. `append` refuses anything else. The
   script stamps `written_at` from the clock and chains `prev` to the sha256 of
   the previous line. Batch ids are unique; a re-planned batch gets a new id.
2. **Append only.** No line is edited, reordered or deleted, including after a
   failed call. A correction is a new entry.
3. **The latest entry is the open batch.** A call may run only points of the
   latest entry written before it, each at most as many times as it is
   registered. Appending the next entry closes the previous one: a point of a
   closed batch is run again only through a new entry.
4. **Points match within tolerance.** A condition is a number, a string, or a
   list or object of them at any depth (a vector, a list of probes); null and
   booleans are refused, write a flag as 0/1 or a string. Two points match when
   they have the same structure (the same keys at every level, lists of the same
   length), numbers equal element by element within rtol 1e-6 and atol 1e-9
   (`--rtol`, `--atol`), and strings equal. Key order does not count, list order
   does: `[3, 0]` matches `[3.0, 0.0]`, not `[0, 3]` or `[3, 0, 0]`. Register
   conditions in the units the call takes, not the effective units of section 7.
5. **A registered point that never ran is allowed.** The gate prints it as a
   `note:`; Known Defects says why. It is not run later from the closed entry
   (rule 3).
6. **Section 6 is copied from the log.** One row per batch that ran, in log
   order; Batch equals the entry's `batch`; Design method equals the entry's
   `design_method`. Justification is `` `type → target` `` when every point
   that ran shares it, otherwise `` <names>: `type → target` `` parts separated
   by `;` (e.g. `` e4: `information → …`; e5, e6: `variance → Km_B` ``) naming
   every point that ran with its logged justification. Each `type → target` is
   copied verbatim inside one pair of backticks; only a `;` (or `<br>`)
   outside backticks separates parts, so a `;` inside a target stays with it.
7. **The time source is not the agent.** `--source` is a record the agent
   does not write: the oracle or simulator log converted to the acquisitions
   format, or the witness file the hook below writes. When the witness exists,
   run the gate on it with `--require-commit`.

The Experiments column of section 6 names every experiment of the batch
(comma-separated, `e1–e12` for a numeric range), with the names used in the
call; RUN and COMPARISON snapshots list the same names, and `{result_gate}`
reads the column when it has no `--source`.

Run before presenting the DATASET, next to `cfs validate`:

`python3 {design_gate} architecture/design_log.jsonl --source <acquisitions> --dataset architecture/DATASET.md [--require-commit]`

Exit 0 PASS, 1 FAIL, 2 usage error or unreadable source. One line per
violation `[Dk] message`, `note:` lines, then PASS or FAIL.

**Acquisitions format.** JSONL, one call per line: `time` (ISO 8601 with an
offset, or epoch seconds) and `points` (a list of `{name, conditions}`, or
label → conditions); optional `design_lines` and `design_head` (the log
commitment); conditions may be vectors and objects (rule 4). Or CSV, one
experiment per row: `time`, optional `call` (rows with one `call` value are one
call) and `name`, every other column a condition. CSV is for scalar conditions
only: a vector in a CSV cell is read as a string and matches no point.

### Design gate (`{design_gate}`)

| ID | The gate fails the DATASET unless |
|----|-----------------------------------|
| D1 | the log exists and every line is a JSON entry with all fields, `seq` 1, 2, … in file order, a unique batch id, at least one point, every point named (unique in its batch) with exactly one justification whose type is from the P5 vocabulary and whose target is set, and a design method (`manual:` with a reason) (rule 1) |
| D2 | the log was only appended to: every `prev` is the sha256 of the line before, `written_at` never decreases, every call's `design_head` equals the sha256 of the log's first `design_lines` lines, and no entry absent at a committed call claims a `written_at` before it (rule 2) |
| D3 | every call ran after an entry was written, and each executed point was registered before its call, not later; with `--require-commit`, every call carries a commitment (rules 1, 3, 7) |
| D4 | every executed point matches an unused registered point of the open entry within tolerance (rules 3, 4) |
| D5 | with `--dataset`: section 6 has one row per batch that ran, in log order, each naming a logged batch, whose Justification gives every point that ran its logged `type → target` (shared or per name; parts split at `;` outside backticks) and whose Design method equals the logged one (rule 6) |

The open entry is the last of the `design_lines` the call committed to, or,
without a commitment, the latest entry whose `written_at` precedes the call.

### Preventing the call (integration point)

The kit does not own the experiment interface; it ships the check, and the
project wires it in. `{design_log} hook` admits a call only if each point is an
unused point of the latest entry, then appends a witness record (time, tool,
`design_lines`, `design_head`, points: the executed conditions as passed, each
with the `name` of the registered point it matched, also when the call itself
names none); otherwise it exits 2 and the call is
blocked. As a Claude Code `PreToolUse` hook in `.claude/settings.json`:

```json
{"hooks": {"PreToolUse": [{"matcher": "mcp__enzyme_simulation__simulate_enzyme_dynamics",
  "hooks": [{"type": "command", "command": "python3 kits/studio-kit-phlogiston/scripts/design_log.py hook --log architecture/design_log.jsonl --witness architecture/design_witness.jsonl --points-key request.conditions"}]}]},
 "permissions": {"deny": ["Edit(architecture/design_witness.jsonl)", "Write(architecture/design_witness.jsonl)"]}}
```

For an experiment CLI, the wrapper runs `{design_log} hook … --points <json>
--tool <name>` and aborts the call on a non-zero exit.

**Sequential analysis (optional).** With `--require-analysis` the hook also
refuses a call that starts a new batch until the previous batch is analysed:
a RUN in `--runs` whose `**Experiments**:` include every experiment of that
batch and, when it is the second batch or later, a COMPARISON in
`--comparisons` that includes them too (defaults: `runs/` and `comparisons/`
next to the log). The first `--free-batches N` batches (default 1) start
without it. The refusal names the batch and what to write; the admitted
call's witness record carries `analysed` with the covering IDs. It is the
mechanical form of RUN rule 10 and COMPARISON rule 5: a batch is designed from
the latest RUN and COMPARISON, never fired off to spend the budget. The design tools
(`propose_doe_experiments`, `fit_parameters`) are not gated: they run no
experiment.

## Where the principles land in a DATASET

| Section | Principles |
|---------|------------|
| 1. Origin and Source | P1 first line: ground-truth / simulator / mixed |
| 4. Units of Measure | P2 every quantity, its unit, its source |
| 5. Axes | P6 Explored range next to Allowed range |
| 6. Acquisition | P1 Origin per batch; P5 Justification and Design method, copied from the design log; P4 Simulator preview; P3 Actual duration; P12 Approved by |
| 8. Known Defects | P3 departures from the confirmed cost |
