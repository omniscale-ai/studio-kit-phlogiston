---
name: literature
description: Invoke when, in a workspace with a research PLAN, the user asks to search, review, or collect values from the literature for that run, however phrased (related work for a paper, a review of a research area, a review of reviews, experimental values from papers), or to cite literature in or put it into the PLAN. Not for summarising a paper the user attached or answering from your own knowledge. Runs one of four fixed strategies (related, review, metareview, scout) and records it as a LITERATURE artifact whose claims are verified before they enter a PLAN.
---

# Literature workflow

One request = one strategy = one LITERATURE artifact. Do not improvise a search: pick one of the four paths below from the human's answers and follow its steps in order. Retrieval and verification are mechanical (`{lit_run}`, `{lit_gate}`; both resolve via `cfs resolve-vars` to workspace-relative script paths); the analysis sections are yours, written over the retrieved Set only.

Load `{principles}`, `{literature_rules}` and `{literature_template}` first. The principles that bind here: P10 (a claim licenses nothing until verified with quote and location), P12 (a human approves the Set before analysis and the rows before they enter a PLAN), P1 (a value taken from a paper is never pooled with a measured one), P7 (a threshold found in the literature is `proposed`, never `confirmed`), P3 (cost stated before running).

## 0. Literature mode - before anything else

1. Locate the run's PLAN: `architecture/PLAN.md`, or the path the human gave. Read its section 2 (`{plan_template}`): **Literature mode** and, under `blind`, the **Excluded** table.
2. No PLAN, no Literature mode line, or mode `none`: **refuse**. Say why (literature enters a PLAN only through a LITERATURE; under `none` only materials the human attached to the run are allowed, marked `given`). No network. Stop.
3. Mode not confirmed by a named person with a date in PLAN section 11: **stop and ask the human to confirm it** (a PLAN not yet approved may be used once the human confirms now). Wait; never assume a mode. Record in section 8: `- Literature mode confirmed by <person>, <YYYY-MM-DD> (<PLAN section 11 | conversation>)`. If the person's name is unknown, ask. The line is not gated.
4. Mode `allowed`: continue to intake.
5. Mode `blind`: read every row of the Excluded table (types `doi`, `title`, `term`, `benchmark`, `author`).
   - Empty table or placeholder rows: stop; the PLAN is not approvable. No network.
   - Without PLAN section 11 approval, the human must confirm the mode **and** the Excluded table, shown row by row, before any `lit_run`. Append `; Excluded table confirmed` to the line of step 3.
   - Never put an excluded item into a query, anchor, subject or must-have term.
   - Match every anchor, title, arXiv id, draft text or subject the human gives against Excluded (case-insensitive; `doi` exact, other types as substring) **before building any query**. On a match **refuse it**, without repeating the matched text beyond what the human needs, and ask for another.
6. Pass `--plan <PLAN.md>` to every `lit_run` and `lit_gate` call, in every mode (the PLAN exists, step 2 refuses otherwise); it fills the Request lines from the PLAN. Never drop `--plan` to get past an exit 2.

## 1. Intake - ask, then stop asking

Ask each question below whose answer is not already given in the request; ask nothing else; then state the cost. Stop as soon as the path is fixed.

1. **Which strategy?** `related`, `review`, `metareview` or `scout` (paths below). If the human describes the need, map it and confirm the mapping in one line.
2. **Anchor or subject.** `related`: a DOI or OpenAlex id. For a title, an arXiv id or a draft file, either ask for the DOI, or put the resolving search in the cost statement (title search: 10 credits; arXiv id: one work lookup of DOI `10.48550/arXiv.<id>`: 1 credit) and search only after the go. Show the resolved paper and get confirmation; under `blind` match its resolved DOI, title and authors against Excluded after resolving. Others: the subject in the human's words plus two or three must-have terms.
3. **Bounds**, only those the strategy takes: years, fields to exclude, open access only; for `scout` the quantity, its unit and the conditions to be reported with it.
4. **Size.** `review`: depth `quick` (~20 papers) or `deep` (snowball, ~100). Other strategies: `-n`, the cap on the total Set.

Output shape is fixed by strategy, not asked: `related` reading list, `review` landscape, `metareview` narrative, `scout` table. Pass it as `--output`.

**State the cost before running**, and **stop and wait for the human's go**. No network call of any kind (including title resolution) before the go. Estimate:

- OpenAlex: search 10 credits, single work 1, group_by 10, ~1000/day keyless (a free key in `OPENALEX_API_KEY` raises the budget tenfold). Add 10 for an anchor-resolving title search, and 1 per DOI in the Set for the online gate.
- Consensus calls, only if configured (1 call per 100 papers; free plan 30/month, shared with the MCP).
- Hypothesis collection: built after the Set gate from the approved Set; covered by this go.
- Full text: the number of open-access PDFs to fetch, with their URLs and hosts, for quotes (Paths 1-3) or values (Path 4). Fetch tool: WebFetch or a file the human provides (ask which if unclear). Each fetch is recorded in Sources; none beyond what the human approved.

## Sources

| source | role | needs |
|---|---|---|
| OpenAlex REST (keyless) | the Set, the citation graph, counts, verification of every DOI; always used | nothing, or a free key |
| Consensus (MCP `mcp.consensus.app`) | evidence ranking; study-type filters; full-text passages on paid plans | MCP configured; account; paid plan for passages |
| Constructor Hypothesis (MCP `constructor.app/api/hypothesis-mcp/streamable-http`) | claims / methods / datasets map, article text, passages and contradictions over a collection built from the approved Set | MCP configured; built collection; 30-day access key |

- "Configured" means the MCP server's tools are present in this session. If not, record the source as `not configured` in section 2. Nothing is substituted silently; a different source in place of a configured one is written as a deviation.
- The script's Consensus and Hypothesis rows are placeholders (environment variables only): overwrite them after the run with ran `yes|no`, tool calls or queries, calls used. OpenAlex rows and the Retrieval line stay as the script wrote them.
- **Always overwrite `Cost stated before running`** (the script writes a placeholder) with the cost as stated to and approved by the human.
- A 401 from Consensus or Hypothesis means the key expired: report, record the source as skipped with the reason, do not retry. An OpenAlex 401 or any `lit_run` exit 1: report and stop; do not unset or replace keys; re-run only if the human says so.

## Retrieval and output

Run `python3 {lit_run} {related|review|metareview|scout} "<query>" --system <system> --out architecture/literature --plan <PLAN.md> --output <shape> [-n N] [--since <year> --depth quick|deep] [--quantity <name> --unit <unit>]`.

- `--system` is required (the PLAN's system slug). The script writes `architecture/literature/<strategy>-<slug>.md` (and for `scout` a CSV skeleton beside it): Request lines, section 2 Sources, section 3 Set (no Approved by line), the section 4 placeholder, the Retrieval line. With `--plan` it also writes PLAN, Literature mode, Exclusions checked and `Removed by exclusion`.
- Exit codes: 0 written; 1 retrieval failed, nothing written; 2 refused (mode `none`, excluded anchor, existing file, usage). Report 1 and 2; do not work around them.
- `--since` and `--depth` only for `review` (exit 2 otherwise). For the other strategies the size is `-n`, a cap on the total Set; under `blind` the cap applies before exclusion, so removed papers leave the Set smaller than `-n` (they are counted, not replaced). Other bounds (years, excluded fields, open access) are not applied by the script: trim rows by hand and record it in Bounds ("Set trimmed by hand: <n> rows, rule ..."), or tell the human the bound is unmet. The Bounds line records only bounds actually applied.
- If the script returns more than `-n`, trim by hand, highest `cited_by` first, and state how many rows were dropped and by which rule before the Set gate. Trimmed rows are not "removed by exclusion"; keep that count, the counts and Cost used consistent.
- Set row numbers are the `#` cells. When trimming or changing the Set, delete rows without renumbering, so citations stay stable.
- **Never pass `--force`** unless the human explicitly instructs it for that file.
- You write sections 5-7 and the approval, hand-over and gate lines of section 8, each approval only after the person gave it.

## Claims, citations, MCP results

- Each section 6 claim carries a quote copied verbatim from text retrieved on this run (OpenAlex abstract, Hypothesis or Consensus passage, OA full text), with its location. Never quote from memory. `verified` only if its Set row has `resolved: yes` and quote and location come from retrieved text; otherwise `assumed`. Quotes may contain the source's own brackets.
- In Analysis, cite Set rows as `[n]` in prose; in section 5 tables only a `set #` column cites rows.
- MCP results never add papers to the Set; use them only for Set papers, matched by DOI. A paper outside the Set is not mentioned unless the human adds the row and the Set gate repeats.
- Under `blind`, screen every outgoing query, every returned title, DOI, author and venue, **and every full-text fetch**: check the passage and the paper's metadata against Excluded before quoting. Hits are dropped, counted in Removed by exclusion, and never named.

## Human gates (P12)

- **Set gate.** Present the Set (for `review` also the Groups). The human approves, trims or adds. Only after the person approved, record the section 3 line `Approved by: <person>, <YYYY-MM-DD>` and the section 8 line `Set approved by <person>, <YYYY-MM-DD>.` Stop and wait. **No analysis before this.**
- **Set change after the gate** (removal, `unresolved` re-marking, added rows): show it to the human and repeat the Set gate. No renumbering; update Removed by exclusion by count only; update `Set approved by` only after the new approval; re-run the gates.
- **Rows gate.** Present the proposed PLAN section 2 rows (and candidate hypotheses). The human approves each row; record `Hand-over to <PLAN ID> section 2: ...; approved by <person>, <YYYY-MM-DD>.` only after that. Stop and wait.

## Path 1 - `related`: what was done before this paper

1. `lit_run related <doi> -n <N> ...` with the anchor resolved in Intake 2. The script fetches the anchor, its references ranked by citations, citers, related works and a same-topic set from a title search; dedupes; writes the draft.
2. Propose the Set (roles: reference / citer / related / same-topic). **Set gate.**
3. Optional, only if configured: Consensus `search` on the anchor's question as an evidence-ranking column; a Hypothesis collection of the approved Set, then `similarity_search` and `search_fulltext_chunks` for key terms; record coverage `k of N` in section 4.
4. Write section 6 Claims.
5. Analysis: group the references by sub-problem; for each, what was established, by whom, with which method, and what the anchor changes or adds. Every sentence about a paper ends with its `[n]`; the anchor is named without a number.
6. Hand over (Closing).

## Path 2 - `review`: the subject area, by groups

A review as its own genre: the groups doing the work named by their authors, their approach, an assessment of their success; non-trivial observations, not a list.

1. `lit_run review "<subject>" [--since <year>] --depth <quick|deep> ...`. The script searches, counts works by year, topic, institution, venue and author, takes anchors (most cited), snowballs one hop when deep, dedupes, and writes the Set and a Groups table.
2. **Set gate**, including the proposed groups (grouped by co-authorship; the human may merge, split or name them).
3. Optional, only if configured: Consensus `search` per group's central question; Hypothesis `graph_entity_search` on method and problem entities, contradiction tools between anchors of different groups.
4. Write section 6 Claims.
5. Analysis: one block per group - who, what they claim, how, since when, what they achieved in the Set's own terms (citations, follow-ups, replication by others), and an assessment (succeeding, stalled, too early to say) with evidence by `[n]`. Then cross-group observations: agreement, contradiction, approaches gaining or abandoned, judged by the year distribution.
6. Where groups contradict, write section 7 candidates: mechanism or effect, the claims it rests on (`<LITERATURE ID>, claim n`), a proposed diagnostic condition, status NOT YET TESTED. Hand over.

## Path 3 - `metareview`: trends from the reviews

Breadth in exchange for depth: primary sources are not read, and the artifact says so.

1. `lit_run metareview "<subject>" ...`. The script restricts to works of type review and works whose title says review, survey, overview, road map or perspective, on the subject's topics, sorted by citations. Optional, only if configured: Consensus `search` with a study-type filter.
2. **Set gate** on the reviews.
3. Write section 6 Claims; each claim is a trend a review asserts, quoted from that review.
4. Analysis: per review its scope, period, trends and gaps; then trends asserted by several reviews, asserted by one and contradicted by another, and what no review covers. Every trend cites its reviews. No claim about a primary source; one that needs it is listed as a candidate for Path 1 or 2.
5. Hand over: nothing enters PLAN section 8 from a meta-review alone, so section 7 is `none` unless a contradiction between reviews supports a candidate.

## Path 4 - `scout`: experimental data from the literature

A data table, one row per measurement: what was measured, how, under which constraints.

1. `lit_run scout "<subject and quantity>" --quantity <name> --unit <unit> ...`. The script ranks abstracts by measurement signals, records each open-access link, and writes the draft and the CSV skeleton. Columns: `set # | paper | doi | link | what_measured | how_measured | constraints | value | unit | passage`.
2. **Set gate.**
3. Full text, in preference order: Hypothesis `search_fulltext_chunks` / `get_full_article` on a collection of the Set; Consensus `search` with `include_full_text_chunks` (paid plan); the OA PDF from OpenAlex. Use only what is configured; fetch only PDFs approved in the cost go, and record each fetch in Sources. No reachable text: row with `what_measured` and `how_measured` from the abstract if stated there and an empty value: **no passage, no value**.
4. `constraints` = limits imposed during the process, in the paper's words. Units are copied as printed, never converted; a conversion the PLAN needs goes in the PLAN's concordance (P2).
5. Write the table in section 5 and the same rows as CSV beside the artifact; section 6 Claims for values the PLAN may use, the quote being the source passage.
6. Hand over proposed PLAN section 2 Prior Knowledge rows as **claims**. **Never** hand over DATASET rows or candidates, never fit a RUN to a value, never pool a value with measurements (P1).

## Closing

Gate exit codes (`{lit_gate}`): 0 PASS; 1 FAIL (fix the cause); 2 usage error (fix your invocation); 3 could not complete (network or IO): report it, and retry later only with the human's go for network.

1. `cfs toc <artifact>`, then `cfs validate`. The draft shown at the Set gate is exempt from validate and the gate.
2. Offline gate: `python3 {lit_gate} architecture/literature/<file>.md --plan <PLAN.md>`. Fix every `[Lk]` violation; Analysis, Claims and Set are yours to correct, the Retrieval facts are not.
3. Online gate: the same with `--resolve`. It needs network and spends one credit per DOI: **ask the human for the go and wait** (a deliberate second confirmation, beyond the cost go). Under `blind` only this online PASS clears `author` items. After an online FAIL, fix the cause and ask for a new go before re-running.
4. Record each gate invocation in section 8 exactly as run (resolved path), one line each: `Gate, offline: \`<invocation>\`, run YYYY-MM-DD: PASS|FAIL; <notes>` and `Gate, online: \`<invocation>\`, run YYYY-MM-DD: PASS|FAIL; <DOIs looked up, credits>`. Fill `Cost used` in section 1 against the stated cost.
5. Status `verified` only after an online PASS with `--resolve` and `--plan` is recorded in that form; until then `draft`. Then `cfs validate`, re-run the offline gate (L9 must pass), and record one more `Gate, offline:` line.
6. If the artifact is not `verified` (online gate declined, FAIL, or Collection below half, an allowed draft outcome and not something to fix): under `blind`, do not hand over; report that blind compliance is not cleared. Under `allowed`, hand over every claim as `assumed` and state that the artifact is a draft. Never present a claim from a draft as `verified`.
7. Hand over to the human the proposed PLAN section 2 rows (claims `<LITERATURE ID>, claim n`, each `verified` or `assumed`) and the candidate hypotheses for section 8. `verified` claims license ranges and mechanisms; `assumed` claims may motivate a diagnostic batch only. A candidate whose cited claims are all `assumed` is marked `assumed only` and is not proposed for section 8 as a mechanism. Thresholds derived from the literature are `proposed` (P7). **Stop and wait for approval.**
   - PLAN not yet approved: after approval it changes, its `LITERATURE drawn on` line lists the artifact id, and the human re-confirms Approval in section 11.
   - PLAN already approved or running: hand over the rows and let the human choose a PLAN amendment (sections 2 and 8 only, then re-approval of section 11) or a new PLAN.
8. The PLAN cites the LITERATURE by id and claim number. The LITERATURE never cites the PLAN's results.
