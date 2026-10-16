# studio-kit-core

A minimal kit for Constructor Studio: five artifact kinds, each with a template and rules, plus shared principles, and the literature workflow with its scripts.

```text
artifacts/PLAN/template.md        PLAN structure            (agent + simulator, domain-neutral)
artifacts/PLAN/rules.md           rules for the agent       (your 5 + 5 agent-specific + principles map)
artifacts/DATASET/template.md     DATASET structure         (agent + simulator, MEASUREMENT/SYNTHESIS axes)
artifacts/DATASET/rules.md        rules for the agent       (your 6 + 6 agent-specific + principles map)
artifacts/RUN/template.md         RUN structure             (one procedure on one data snapshot: fit, test, optimisation, …)
artifacts/RUN/rules.md            rules for the agent       (11 rules + principles map)
artifacts/COMPARISON/template.md  COMPARISON structure      (candidates on one snapshot: vectors, dominance, selection, open pairs)
artifacts/COMPARISON/rules.md     rules for the agent       (9 rules + result gate table + principles map)
artifacts/LITERATURE/template.md  LITERATURE structure      (one literature request along one of four strategies)
artifacts/LITERATURE/rules.md     rules for the agent       (12 rules + gate table + principles map)
artifacts/LITERATURE/examples/    worked example            (Path 1, related work, gate PASS online with --plan)
workflows/literature.md           literature workflow       (intake, four strategies, human gates)
scripts/lit_run.py                literature retrieval      (OpenAlex REST, stdlib only; writes the draft LITERATURE)
scripts/lit_gate.py               LITERATURE gate           (L1–L11; --resolve for DOIs; --resolve and --plan for verified)
scripts/lit_common.py             shared literature code    (parsing and exclusion matching used by lit_run and lit_gate)
scripts/design_log.py             design pre-registration   (append-only log of batches; PreToolUse hook that blocks unregistered calls)
scripts/design_gate.py            DATASET design gate       (D1–D5: log integrity, registered before run, conditions, section 6 copy)
scripts/result_gate.py            final-result gate         (R1–R6: final snapshot, structural alternatives, copied vectors, submission = selection, stopping rule, structure; hook with witness)
tests/test_literature.py          literature tests          (gate and retrieval: the shipped example, planted errors, blind exclusions, offline stubs)
tests/test_design.py              design gate tests         (honest run, retroactive log, mismatched points, rewritten log, hook)
tests/test_result.py              result gate tests         (PASS, one FAIL per check R1–R6, stopping rule with and without budget, hook witness)
tests/fixtures/                   test fixtures             (PLANs in modes allowed, blind, none; design/: log, oracle, DATASET)
principles.md                     12 cross-cutting invariants, loaded first by every rules.md
AGENTS.md                         agent quick reference, public rule: lands in the project's generated AGENTS.md
constraints.toml                  headings + IDs for cfs validate (generated from the templates)
.cf-studio-kit.toml               manifest
```

## What remains to be done

1. Proofread the rules and templates: the structure is taken from Phlogiston (`app/agents.py`, `prompts.md`, `vendor/doe/mcp`), domain
   constants are moved into placeholders, the enzyme case is kept as an example. The criterion thresholds are yours to set.
2. When changing a heading in `template.md`, mirror the `pattern` in `constraints.toml`.
   Curly braces in the templates are not filled in; they are hints for the agent.

## How to add it to a project

```bash
cd <project where Studio is installed>
cfs kit install --path ./kits/studio-kit-phlogiston --install-mode register   # path inside the project root; the directory name is arbitrary
cfs validate-kits
```

Then register the system in the project's `artifacts.toml` (verified end-to-end for PLAN, DATASET, RUN and COMPARISON):

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

[systems.autodetect.artifacts.LITERATURE]
pattern = "literature/*.md"
traceability = "DOCS-ONLY"
required = false
```

After that, `cf-write-docs: write the PLAN for ...` uses your template and rules, `cfs toc <file>` generates the
table of contents, and `cfs validate` checks headings, IDs and references. Every document starts with frontmatter containing a `description` field, otherwise `cfs validate` warns. In documents the ID is written as the line `**ID**: \`cpt-core-plan-<slug>\``
with no checkbox and no priority.

## How to bring back deferred items

Deferred items are kept outside this kit; to bring one back, copy it into the kit and register it.
Artifact kind: copy its `artifacts/<KIND>/` directory in, add two resources to the manifest
(`<kind>_template`, `<kind>_rules`) and a headings block to `constraints.toml`.
Checklist: copy the file in, add a resource with `kind = "checklist"`. Needed only for semantic review.
Workflow: copy it into `workflows/`, add a resource with `kind = "skill"`, `public = true`.

## Literature block

A fifth artifact kind, LITERATURE, and the workflow that produces it. One
request = one of four fixed strategies = one artifact:

| strategy | what it delivers | mechanical part (`scripts/lit_run.py`) | the agent's part |
|---|---|---|---|
| `related` | what was done before one paper | references, citers, related and same-topic works from OpenAlex | prior work grouped by sub-problem, each assertion citing a Set row |
| `review` | the subject area by groups | landscape counts by year/topic/institution/venue/author; anchors; one-hop snowball; a Groups table from co-authorship | one block per group with an assessment and its evidence; cross-group observations |
| `metareview` | trends from the reviews only | reviews restricted to the subject's topics and words | per-review scope, period, trends, gaps; agreement and contradiction between reviews; no primary-source claim |
| `scout` | a data table | candidates ranked by measurement signals, OA links, CSV skeleton | one row per measurement with the passage it came from; no passage, no value |

`workflows/literature.md` is the procedure (intake questions, the path's
steps, where a human approves). `artifacts/LITERATURE/{template,rules}.md`
define the record; `constraints.toml` and the manifest register it.

Literature mode. Every PLAN of an agent run states it in section 2, Prior
Knowledge, and a human confirms it at PLAN approval; there is no default.

| mode | what it allows |
|---|---|
| `none` | no literature is searched and no LITERATURE is produced (the literature workflow refuses to run); materials a human attached in the run's `literature` field remain allowed, marked `given` in the PLAN's section 2, and are the only literature the PLAN may cite |
| `allowed` | besides the attached materials, literature enters the PLAN only through LITERATURE artifacts, cited as `<LITERATURE ID>, claim n` |
| `blind` | as `allowed`, plus the PLAN's Excluded table: items (`doi`, `title`, `term`, `benchmark`, `author`) that must not be retrieved or cited because they could reveal the answer; attached materials are checked against the Excluded table by the human at Approval (the gate does not see them) |

Under `blind` an excluded item is matched case-insensitively (LITERATURE
rule 11): a `doi` item exactly against a DOI cell and against a DOI embedded
in an OA link, and as a substring in free text; the other types as a
substring. The gate matches only when run with `--plan`, which supplies the
Excluded table. It then scans every cell of every Set row; Analysis, Claims,
Candidate Hypotheses and the Request; each query of the Sources query
column, also URL-decoded (a query that contains an excluded item means it
was retrieved); the H1 title and the frontmatter description; section 3
outside the Set table; the scout CSV; and the whole raw text of the file,
HTML comments and code fences included. Venue and authors are not Set
columns and are compared only with `--resolve`, against the OpenAlex record
of each row that has a DOI. An offline PASS under `blind` therefore does not
clear `author` items; only the online PASS with `--plan` does. A matched
paper is removed from the Set and counted in Sources, never named.

Values found by `scout` stay in the LITERATURE: a table in the artifact plus
the CSV beside it. They reach a PLAN only as claims in its section 2: a `verified` claim
may license a parameter range or a hypothesis; an `assumed` one may
motivate a diagnostic batch only. They
never become a DATASET; there is no `literature` origin, and no RUN fits
them.

The gate:

```bash
python3 scripts/lit_gate.py <file>.md [--plan <PLAN.md>] [--resolve]
```

Exit 0 PASS, 1 FAIL, 2 usage error, 3 could not complete (network or file
error; no verdict). The checks are L1–L11 in the LITERATURE rules. On every
invocation it refuses an artifact whose Set rows lack a unique positive
integer `#`; whose `verified` claims lack a quote or a location or rest on a
row not resolved `yes`; whose Analysis cites Set rows that do not exist or
cites none (citations are read from prose outside tables and code; a scout
table cites by its `set #` column); whose candidate hypotheses cite no
existing claim or are not NOT YET TESTED; whose Set approval lacks a person
and a date; whose Sources `ran` cells are outside `yes`, `no`,
`skipped (<reason>)`, `not configured`; whose scout CSV and scout table
differ in row count or carry a value without a passage; or, when it is
`verified`, whose Hypothesis collection holds less than half the approved
set. With `--resolve` it looks up every DOI in OpenAlex (network). With
`--plan` it reads the PLAN's Literature mode and Excluded table and fails if
the PLAN's mode is `none`, if the Request's `PLAN:` ID or Literature mode
differs from the PLAN's, or, under `blind`, on any excluded hit or if
`Exclusions checked` differs from the PLAN's Excluded row count; without
`--plan` it passes only a Request whose Literature mode is exactly
`allowed`.

A LITERATURE becomes `verified` only after a PASS of an online invocation
that has both `--resolve` and `--plan`; a run without `--plan` is a
structural check only and never clears blind compliance. The gate checks
that such a PASS is attested in the artifact, not that the run happened. Of
the Attestation it reads only the `Set approved by` line and the
`Gate, online:` lines; the others, including the line recording who
confirmed the literature mode, are for the record. The PLAN's
`LITERATURE drawn on` line is not checked by the gate; the PLAN author keeps
it complete at Approval.

`scripts/lit_run.py` writes the mechanical parts of the draft and refuses to
overwrite an existing artifact or CSV (exit 2, before any request) unless
`--force` is given. `--since` and `--depth` apply only to `review`; for the
other strategies `-n` caps the total Set. `Cost stated before running` is
the agent's estimate; `Cost used` is written by the script for retrieval and
completed by the agent with the gate's DOI lookups.
`tests/test_literature.py` gates the shipped example, planted errors in
scratch copies of it, and the PLAN fixtures in `tests/fixtures/`.

## Installing the literature sources

The kit ships no key. The minimum is OpenAlex, keyless: retrieval and DOI
verification run on it alone. Consensus and Constructor Hypothesis are
optional MCP sources; a source that is not configured is skipped and the
artifact's Sources section says so.

What the user must supply:

| source | access | the user supplies |
|---|---|---|
| OpenAlex | REST keyless (about 1000 credits a day: search = 10, work = 1, group_by = 10; a title search to resolve an anchor 10; the online gate 1 per DOI); MCP `https://mcp.openalex.org/mcp` | nothing for keyless REST; optionally a free OpenAlex account and key in `OPENALEX_API_KEY` for ten times the budget, or for the MCP, which needs a sign-in through the browser once |
| Consensus | REST `https://api.consensus.app/v1/search` (header `x-api-key`); MCP `https://mcp.consensus.app/mcp` | a Consensus account and a key in `CONSENSUS_API_KEY` (profile menu, API & MCP Dashboard, Keys and clients, New key; shown once); the free plan gives 30 calls a month, shared with its MCP; full-text passages, overage and recurring use need a paid plan |
| Constructor Hypothesis | MCP `https://constructor.app/api/hypothesis-mcp/streamable-http`, header `X-Model-AccessKey` | a Constructor Hypothesis account; a collection relevant to the run, built (uploads, Zotero or the product's search) and indexed before the workflow runs; an access key in `HYPOTHESIS_MCP_KEY`, renewed every 30 days |

MCP entries for Claude Code:

```bash
claude mcp add --transport http openalex   https://mcp.openalex.org/mcp
claude mcp add --transport http consensus  https://mcp.consensus.app/mcp
claude mcp add --transport http hypothesis https://constructor.app/api/hypothesis-mcp/streamable-http \
    --header "X-Model-AccessKey: $HYPOTHESIS_MCP_KEY"
```

Environment for scripted access:

```bash
export OPENALEX_API_KEY=...      # optional: ten times the keyless OpenAlex budget
export CONSENSUS_API_KEY=...     # required for any Consensus REST call
export HYPOTHESIS_MCP_KEY=...    # required for the Hypothesis MCP; renew every 30 days
```

Each LITERATURE's Sources section records which sources ran; a project may
list its configured sources in its CLAUDE.md.
