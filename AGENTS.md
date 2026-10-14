# Constructor Studio Kit: studio-kit-core (`studio-kit-core`)

Agent quick reference for simulator-backed research runs.

## What it is

Five artifact kinds that make an agent's research run inspectable: a PLAN that gates the work, a DATASET that records what was acquired and why, a RUN per procedure execution with its own verdict, a COMPARISON per snapshot where selection happens, and a LITERATURE per literature request so that nothing licenses a range or mechanism in a PLAN from the literature unverified. Twelve cross-cutting principles bind all five.

## Artifact kinds

| Kind | Semantic intent (when to use) | References |
| --- | --- | --- |
| PLAN | One agent run: question, datasets and origin, human-confirmed simulation cost, budget, phases, design policy, hypothesis register, agreed and frozen verdict criteria, approval. | `{plan_rules}`, `{plan_template}` |
| DATASET | Every experiment acquired in one run: origin (ground-truth / simulator / mixed), apparatus, units of measure, allowed and explored axes, justified batches in order, defects, provenance. | `{dataset_rules}`, `{dataset_template}` |
| RUN | One execution of one procedure on one dataset snapshot: candidate spec, settings, licensed assumptions, outputs, its own verdict vector, handoff to the next design. | `{run_rules}`, `{run_template}` |
| COMPARISON | All candidate RUNs on one snapshot in one phase: criterion vectors, pairwise dominance, selection under the PLAN rule, open pairs, hypothesis status updates. | `{comparison_rules}`, `{comparison_template}` |
| LITERATURE | One literature request along one of four strategies (related, review, metareview, scout): approved Set, verified claims, candidate hypotheses; the only way searched literature enters a PLAN (materials the human attached to the run are cited as `given`). | `{literature_rules}`, `{literature_template}`, `{literature_workflow}` |

## Navigation rules

ALWAYS open and follow `{principles}` WHEN authoring or reviewing any PLAN, DATASET, RUN, COMPARISON or LITERATURE

ALWAYS open the kind's `rules.md` and `template.md` from the table above WHEN authoring that kind

ALWAYS run `cfs validate` on every written artifact before presenting it; for a LITERATURE also run `python3 {lit_gate} <file> --plan <PLAN>` once the analysis is written; the draft Set shown at the Set gate is exempt from both `cfs validate` and the gate; run `--resolve` only after the human's go (network, credits); `verified` needs that online PASS with `--plan`; follow `{literature_workflow}` Closing

ALWAYS follow `{literature_workflow}` WHEN literature is to be searched, cited or put into a PLAN

NEVER search literature WHEN there is no PLAN, its Literature mode is `none`, or the mode is not yet confirmed by the human

NEVER run `{lit_run}` before stating the cost and receiving the human's go

NEVER write LITERATURE analysis before the human has approved the Set

NEVER pass `--force` to `{lit_run}` unless the human instructs it for that file

NEVER write an Approved by, Set approved by or Hand-over line the person did not give

ALWAYS pass `--plan` to `{lit_run}` and `{lit_gate}` in every mode (a PLAN file must exist; mode `none` or no PLAN refuses)

NEVER retrieve or cite an item from the PLAN's Excluded table under `blind`

NEVER cite a paper that is neither attached to the run nor in a LITERATURE Set

NEVER turn a value found in a paper into a DATASET row or fit a RUN to it

NEVER change verdict criteria, thresholds or the selection rule outside a new PLAN
