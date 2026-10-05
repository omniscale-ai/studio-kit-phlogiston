# Constructor Studio Kit: studio-kit-core (`studio-kit-core`)

Agent quick reference for simulator-backed research runs.

## What it is

Four artifact kinds that make an agent's research run inspectable: a PLAN that gates the work, a DATASET that records what was acquired and why, a RUN per procedure execution with its own verdict, and a COMPARISON per snapshot where selection happens. Twelve cross-cutting principles bind all four.

## Artifact kinds

| Kind | Semantic intent (when to use) | References |
| --- | --- | --- |
| PLAN | One agent run: question, datasets and origin, human-confirmed simulation cost, budget, phases, design policy, hypothesis register, agreed and frozen verdict criteria, approval. | `{plan_rules}`, `{plan_template}` |
| DATASET | Every experiment acquired in one run: origin (ground-truth / simulator), apparatus, units of measure, allowed and explored axes, justified batches in order, defects, provenance. | `{dataset_rules}`, `{dataset_template}` |
| RUN | One execution of one procedure on one dataset snapshot: candidate spec, settings, licensed assumptions, outputs, its own verdict vector, handoff to the next design. | `{run_rules}`, `{run_template}` |
| COMPARISON | All candidate RUNs on one snapshot in one phase: criterion vectors, pairwise dominance, selection under the PLAN rule, open pairs, hypothesis status updates. | `{comparison_rules}`, `{comparison_template}` |

## Navigation rules

ALWAYS open and follow `{principles}` WHEN authoring or reviewing any PLAN, DATASET, RUN or COMPARISON

ALWAYS open the kind's `rules.md` and `template.md` from the table above WHEN authoring that kind

ALWAYS run `cfs validate` on the written artifact before presenting it

NEVER change verdict criteria, thresholds or the selection rule outside a new PLAN
