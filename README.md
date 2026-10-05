# studio-kit-core

A minimal kit for Constructor Studio: four artifact kinds, each with a template and rules, plus shared principles.

```
artifacts/PLAN/template.md        PLAN structure            (agent + simulator, domain-neutral)
artifacts/PLAN/rules.md           rules for the agent       (your 5 + 5 agent-specific + principles map)
artifacts/DATASET/template.md     DATASET structure         (agent + simulator, MEASUREMENT/SYNTHESIS axes)
artifacts/DATASET/rules.md        rules for the agent       (your 6 + 6 agent-specific + principles map)
artifacts/RUN/template.md         RUN structure             (one procedure on one data snapshot: fit, test, optimisation, …)
artifacts/RUN/rules.md            rules for the agent       (10 rules + principles map)
artifacts/COMPARISON/template.md  COMPARISON structure      (candidates on one snapshot: vectors, dominance, selection, open pairs)
artifacts/COMPARISON/rules.md     rules for the agent       (7 rules + principles map)
principles.md                     12 cross-cutting invariants, loaded first by every rules.md
AGENTS.md                         agent quick reference, public rule: lands in the project's generated AGENTS.md
constraints.toml                  headings + IDs for cfs validate (generated from the templates)
.cf-studio-kit.toml               manifest
_later/                           everything deferred: 4 kinds, checklists, workflows, gates, full manifest
```

## What remains to be done

1. Proofread the rules and templates: the structure is taken from Phlogiston (`app/agents.py`, `prompts.md`, `vendor/doe/mcp`), domain
   constants are moved into placeholders, the enzyme case is kept as an example. The criterion thresholds are yours to set.
2. When changing a heading in `template.md`, mirror the `pattern` in `constraints.toml`.
   Curly braces in the templates are not filled in; they are hints for the agent.

## How to add it to a project

```bash
cd <project where Studio is installed>
cfs kit install --path ./kits/studio-kit-core --install-mode register   # path inside the project root
cfs validate-kits
```

Then register the system in the project's `artifacts.toml` (verified end-to-end):

```toml
[[systems]]
name = "Core"
slug = "core"
kit = "studio-kit-core"
children = []

[[systems.autodetect]]
kit = "studio-kit-core"
system_root = "{project_root}"
artifacts_root = "architecture"

[systems.autodetect.artifacts.PLAN]
pattern = "PLAN.md"
traceability = "DOCS-ONLY"
required = true

[systems.autodetect.artifacts.DATASET]
pattern = "DATASET.md"
traceability = "DOCS-ONLY"
required = false

[systems.autodetect.artifacts.RUN]
pattern = "runs/*.md"
traceability = "DOCS-ONLY"
required = false

[systems.autodetect.artifacts.COMPARISON]
pattern = "comparisons/*.md"
traceability = "DOCS-ONLY"
required = false
```

After that, `cf-write-docs: write the PLAN for ...` uses your template and rules, `cfs toc <file>` generates the
table of contents, and `cfs validate` checks headings, IDs and references. Every document starts with frontmatter containing a `description` field, otherwise `cfs validate` warns. In documents the ID is written as the line `**ID**: \`cpt-core-plan-<slug>\``
with no checkbox and no priority.

## How to bring back deferred items

Artifact kind: move `_later/artifacts/<KIND>/` back, add two resources to the manifest
(`<kind>_template`, `<kind>_rules`) and a headings block to `constraints.toml`.
Checklist: move the file back, add a resource with `kind = "checklist"`. Needed only for semantic review.
Workflow: `_later/workflows/*.md`, resource with `kind = "skill"`, `public = true`.
