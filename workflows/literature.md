---
name: literature
description: Invoke when, in a workspace with a research PLAN, the user asks to search, review, or collect values from the literature for that run, however phrased (related work for a paper, a review of a research area, a review of reviews, experimental values from papers), or to cite literature in or put it into the PLAN. Not for summarising a paper the user attached or answering from your own knowledge. Runs one of four fixed strategies (related, review, metareview, scout) and records it as a LITERATURE artifact whose claims are verified before they enter a PLAN.
---

# Literature workflow

One request = one strategy = one LITERATURE artifact. Do not improvise a search: pick one of the four paths below from the human's answers and follow its steps in order. Retrieval and verification are mechanical (`scripts/lit_run.py`, `scripts/lit_gate.py`); the analysis sections are yours, written over the retrieved Set only.

Script paths are relative to the kit root: the directory holding `.cf-studio-kit.toml` (resolve with `cfs resolve-vars`; the variable `{literature_rules}` lives in `<kit>/artifacts/LITERATURE/`). Write `<kit>` for that directory below.

Load `{principles}`, `{literature_rules}` and `{literature_template}` first. The principles that bind here: P10 (a claim licenses nothing until verified with quote and location), P12 (a human approves the Set before analysis and the rows before they enter a PLAN), P1 (a value taken from a paper is never pooled with a measured one), P7 (a threshold found in the literature is `proposed`, never `confirmed`).

## 0. Literature mode - before anything else

1. Locate the run's PLAN: `architecture/PLAN.md` in the workspace, or the path the human gave. Read its section 2 (`{plan_template}`): **Literature mode** and, under `blind`, the **Excluded** table.
2. No PLAN, no Literature mode line, or mode `none`: **refuse**. Say why (literature enters a PLAN only through a LITERATURE, and a PLAN without a confirmed mode `allowed` or `blind` has none; under `none` only materials the human attached to the run are allowed, marked `given` in the PLAN). Do not search. Stop.
3. Mode present but not confirmed by a named person with a date, in PLAN section 11 or in this conversation: **stop and ask the human to confirm it**. Wait. Never assume a mode. A PLAN not yet approved may be used if the human confirms the mode now; record who confirmed it and when in section 8.
4. Mode `allowed`: continue to intake.
5. Mode `blind`: read every row of the Excluded table (types `doi`, `title`, `term`, `benchmark`, `author`).
   - Empty table or placeholder rows: stop; the PLAN is not approvable. Do not search.
   - Never put an excluded item into a query, anchor, subject or must-have term.
   - If the anchor or subject the human gives matches an excluded item (case-insensitive; `doi` exact, other types as substring), **refuse that anchor**, without repeating the matched text beyond what the human needs, and ask for another.
   - Pass `--plan <PLAN.md>` to every `lit_run.py` and `lit_gate.py` call below. Never drop `--plan` to get past an exit 2.
6. Under `allowed`, also pass `--plan <PLAN.md>` whenever a PLAN file exists; it fills the Request lines from the PLAN.

## 1. Intake - ask, then stop asking

Ask in order; stop as soon as the path is fixed:

1. **Which strategy?** `related`, `review`, `metareview` or `scout` (definitions below). If the human describes the need rather than naming it, map it and confirm the mapping in one line.
2. **Anchor or subject.** `related`: a DOI or OpenAlex id. If the human gives a title, an arXiv id or a draft file, resolve it to a DOI before the cost statement with at most one OpenAlex title search (counted in the cost: 10 credits); under `blind`, match the resolved DOI, title and authors against the Excluded table before `lit_run`; show the resolved paper to the human and get confirmation; if it cannot be resolved, ask for a DOI. Others: the subject in the human's words plus two or three must-have terms. Under `blind`, re-run the Excluded match of step 0.5 on the anchor or subject given.
3. **Bounds.** Years; fields to exclude; open access only; for `scout`: the quantity, its unit, and the conditions that must be reported with it. Retrieval and output says which bounds the script applies.
4. **Depth.** `quick` (one pass, ~20 papers) or `deep` (snowball, ~100).
5. **Output shape.** Reading list; landscape; table (`scout`); narrative.

Then **state the cost before running** (P3) and **stop and wait for the human's go**:

- OpenAlex credits: search = 10, work = 1, ~1000/day keyless (a free key in `OPENALEX_API_KEY` raises the budget tenfold).
- Consensus calls, only if its MCP server is configured (1 call per 100 papers; free plan 30/month, shared with the MCP).
- Whether a Hypothesis collection exists for the subject (only if its MCP server is configured).
- The online gate later spends one credit per DOI; include it in the estimate.
- Full text: the number of open-access PDFs to fetch for quotes (Paths 1-3) or values (Path 4), with their hosts. Each fetch is recorded in Sources; none beyond what the human approved.

## Sources and when each is used

| source | role in every path | needs |
|---|---|---|
| OpenAlex REST (keyless) | the Set, the citation graph, the counts, and verification of every DOI. The MVP; always used | nothing, or a free key |
| Consensus (MCP server `mcp.consensus.app`) | evidence ranking; study-type filters; full-text passages on paid plans | MCP server configured; account; paid plan for passages |
| Constructor Hypothesis (MCP server `constructor.app/api/hypothesis-mcp/streamable-http`) | claims / methods / datasets map, article text, passages and contradictions over a collection the human built from the approved Set | MCP server configured; built collection; 30-day access key |

- Consensus and Hypothesis are used only through their MCP servers. If a server is not configured, record the source as `not configured` in section 2 Sources. Nothing is substituted silently; a different source in place of a configured one is written as a deviation.
- A 401 from Consensus or Hypothesis means the key expired: report it, record that source as skipped with the reason, do not retry. An OpenAlex 401 or any `lit_run.py` exit 1: report and stop; do not unset or replace keys and do not re-run unless the human says so.
- The script's Consensus and Hypothesis rows reflect environment variables only. After using an MCP source, edit its row (ran `yes`, tool calls or queries, calls used). Copy the cost stated to the human into Request `Cost stated before running`. The OpenAlex rows and the Retrieval line stay as the script wrote them.

## Retrieval and output

Run `python3 <kit>/scripts/lit_run.py {related|review|metareview|scout} "<query>" --system <system> --out architecture/literature [--plan <PLAN.md>] [-n N] [--since <year>] [--depth quick|deep] [--quantity <name>] [--unit <unit>] [--output <shape>]`.

- `--system` is required (the PLAN's system slug). `--out` defaults to `architecture/literature`, the workspace artifacts root; files there match the LITERATURE pattern `literature/*.md`.
- The script writes `architecture/literature/<strategy>-<slug>.md` (the slug carries a short hash of the query) and, for `scout`, the CSV skeleton beside it. It writes the Request lines, section 2 Sources, section 3 Set (without the Approved by line), the section 4 placeholder and the Retrieval line of section 8. With `--plan` it also writes the PLAN, Literature mode and Exclusions checked lines and `Removed by exclusion`; without it you write those from the PLAN.
- Exit codes: 0 written; 1 retrieval failed, nothing written; 2 refused (mode `none`, excluded anchor, existing file, usage). Report 1 and 2 to the human; do not work around them.
- Pass `-n` so the Set matches the size chosen in Intake 4. If the script returns more, trim by hand, highest `cited_by` first, and state how many rows were dropped and by which rule before the Set gate. Trimmed rows are not "removed by exclusion": keep Removed by exclusion, the counts and Cost used consistent.
- Bounds: the script enforces only `--since`, and only for `review`. Other bounds (years in other strategies, excluded fields, open access only) are not applied. Either trim the Set rows by hand before the Set gate and record it in the Bounds line ("Set trimmed by hand: <n> rows, rule ..."), or tell the human the bound is unmet. Never claim a bound that was not applied.
- The script refuses to overwrite an existing artifact or CSV. **Never pass `--force` unless the human explicitly instructs it for that file.**
- You write sections 5-7 and the approval, hand-over and gate lines of section 8, each approval only after the person gave it.

## Claims (all paths)

Each section 6 claim carries a quote copied verbatim from text retrieved on this run (OpenAlex abstract, Hypothesis passage, Consensus passage, OA full text), with the location saying where. Never quote from memory. A claim is `verified` only if its Set row has `resolved: yes` and quote and location come from retrieved text; otherwise `assumed`.

## MCP results

- Results never add papers to the Set. Use them only for Set papers, matched by DOI. A paper outside the Set is not mentioned unless the human adds the row and the Set gate repeats.
- Under `blind`, screen every outgoing tool query and every returned title, DOI, author and venue against Excluded. Hits are dropped, counted in Removed by exclusion, and never named.

## Human gates (P12)

- **Set gate.** Present the Set (and for `review` the Groups). The human approves, trims or adds. Only after the person has given approval, record the section 3 line `Approved by: <person>, <YYYY-MM-DD>` and the section 8 line `Set approved by <person>, <YYYY-MM-DD>.` Never write them on your own authority. Stop and wait. No analysis before this.
- **Rows gate.** Present the proposed PLAN section 2 rows (and candidate hypotheses). The human approves each row before it enters the PLAN; record `Hand-over to <PLAN ID> section 2: ...; approved by <person>, <YYYY-MM-DD>.` only after that. Stop and wait.

## Path 1 - `related`: what was done before this paper

Purpose: the summary of prior work that every paper carries.

1. Run `lit_run.py related <doi> -n <N> ...` with the anchor resolved in Intake 2. The script fetches the anchor, its references ranked by citations, the works that cite it, the related works and a same-topic set from a search on its title; dedupes; writes the draft with the Request, Sources and Set filled.
2. Propose the Set (roles marked: reference / citer / related / same-topic). **Set gate.**
3. Optional, only if configured (see MCP results): Consensus `search` on the anchor's question, as an evidence-ranking column of the Set. Optional: a Hypothesis collection of the approved Set, then `similarity_search` and `search_fulltext_chunks` for the anchor's key terms; record coverage `k of N` in section 4.
4. Write section 6 Claims (see Claims).
5. Analysis (section 5): group the references by the sub-problem they address; for each, what was established, by whom, with which method, and what the anchor changes or adds. Every sentence asserting something about a paper ends with its Set row number in brackets; the anchor is named without a row number.
6. Hand over (see Closing).

## Path 2 - `review`: the subject area, by groups

Purpose: a review as its own genre: a larger body of work, the groups doing it named by their authors, their approach, an assessment of their success or its likelihood. Non-trivial observations, not a list.

1. `lit_run.py review "<subject>" [--since <year>] --depth <quick|deep> ...`, with the human's answers to Intake 3 and 4. The script searches, counts works by year, topic, institution, venue and author, takes the anchors (most cited in the Set), snowballs one hop from them when deep, dedupes, and writes the draft with the Set and a Groups table (most productive authors with institutions, years active, output in the Set, citations).
2. **Set gate**, including the proposed groups (the script groups by co-authorship; the human may merge, split or name groups).
3. Optional, only if configured (see MCP results): Consensus `search` per group's central question; Hypothesis collection, `graph_entity_search` on the subject's method and problem entities, contradiction tools between anchors of different groups.
4. Write section 6 Claims (see Claims).
5. Analysis (section 5): one block per group - who (authors, institutions), what they claim, how (method, data), since when, what they have achieved in the Set's own terms (citations, follow-ups by others, replication by other groups), and an assessment: succeeding, stalled, or too early to say, with the evidence cited by Set row. Then the cross-group observations: where groups agree, where they contradict, which approaches are gaining and which are being abandoned, judged by the year distribution of the Set.
6. Where groups contradict, write section 7 candidate hypotheses: mechanism or effect, the claims it rests on (`<LITERATURE ID>, claim n`), a proposed diagnostic condition, status NOT YET TESTED. Hand over (see Closing).

## Path 3 - `metareview`: trends from the reviews

Purpose: breadth in exchange for depth. Primary sources are not read; the reviews are. The artifact says so.

1. `lit_run.py metareview "<subject>" ...`. The script restricts to works of type review, to the subject's own topics and to the words in title or abstract; adds works whose title says review, survey, overview, road map or perspective; sorts by citations. Optional, only if configured (see MCP results): Consensus `search` with a study-type filter for reviews and meta-analyses.
2. **Set gate** on the set of reviews.
3. Write section 6 Claims (see Claims); each claim is a trend a review asserts, quoted from that review.
4. Analysis (section 5): for each review - its scope, the period it covers, the trends it asserts, the gaps it names. Then the synthesis: trends asserted by more than one review, trends asserted by one and contradicted by another, and what no review covers. Every trend cites the reviews that assert it. No claim about a primary source appears; a claim that needs one is listed as a candidate for Path 1 or 2.
5. Hand over (see Closing): nothing enters PLAN section 8 from a meta-review alone, so section 7 is `none` unless a contradiction between reviews supports a candidate.

## Path 4 - `scout`: experimental data from the literature

Purpose: a data table. Each paper is analysed for what was measured, how, and under which constraints the process ran. Output: an array with few columns.

1. `lit_run.py scout "<subject and quantity>" --quantity <name> --unit <unit> ...`. The script searches, ranks abstracts by measurement signals, records the open-access full-text link for each, and writes the draft with the CSV skeleton beside it. The table has the columns `paper | doi | link | what_measured | how_measured | constraints | value | unit | passage`.
2. **Set gate.**
3. Full text (see MCP results), in this order of preference: Hypothesis `search_fulltext_chunks` and `get_full_article` on a collection of the Set; Consensus `search` with `include_full_text_chunks` (paid plan); the open-access PDF from OpenAlex. Use only what is configured; fetch only the PDFs the human approved in the cost statement and record each fetch in Sources. A paper with no reachable text gets a row with `what_measured` and `how_measured` from the abstract if stated there, and an empty value: **no passage, no value**.
4. Extraction: one row per measurement, not per paper. `constraints` means the limits imposed during the process (temperature window, sample preparation, instrument range, exclusions) in the paper's words. Units are copied as printed, never converted; a conversion the PLAN needs is written in the PLAN's concordance (P2).
5. Write the table in section 5 and the same rows as CSV beside the artifact. Write section 6 Claims (see Claims) for the values the PLAN may use: the quote is the passage the value came from.
6. Hand over (see Closing): proposed PLAN section 2 Prior Knowledge rows as **claims** (`<LITERATURE ID>, claim n`). The table and the CSV stay in the LITERATURE. **Never** hand over DATASET rows or candidates, never fit a RUN to a value, never pool a value with measurements (P1).

## Closing

Gate exit codes: 0 PASS, 1 FAIL, 2 usage (2 means your invocation is wrong, not a result).

1. Run `cfs toc <artifact>`, then `cfs validate` on the artifact.
2. Gate offline: `python3 <kit>/scripts/lit_gate.py architecture/literature/<file>.md --plan <PLAN.md>`. Fix every `[Lk]` violation; the Analysis, Claims and Set are yours to correct, the Retrieval facts are not.
3. Gate online: `python3 <kit>/scripts/lit_gate.py architecture/literature/<file>.md --plan <PLAN.md> --resolve`. It needs network and spends credits: **ask the human for the go and wait.** Under `blind` only this online PASS clears `author` items. After an online FAIL, fix the cause and ask for a new go before re-running `--resolve`.
4. Record each gate invocation in section 8 exactly as run, one line each: `Gate, offline: \`<invocation>\`, run YYYY-MM-DD: PASS|FAIL; <notes>` and `Gate, online: \`<invocation>\`, run YYYY-MM-DD: PASS|FAIL; <DOIs looked up, credits>`. Also fill `Cost used` in section 1 (retrieval plus the online gate's lookups against the stated cost).
5. Set status `verified` only after an online PASS with both `--resolve` and `--plan` is recorded in the Attestation in that exact form; until then `draft`. Then run `cfs validate` and re-run the offline gate with `--plan` (L9 must pass), and record one more `Gate, offline:` line.
6. If the artifact is not `verified` (online gate declined, FAIL, or Collection below half): under `blind`, do not hand over; stop and report that blind compliance is not cleared. Under `allowed`, hand over every claim as `assumed` only and state that the artifact is a draft. Never present a claim as `verified` from a draft.
7. Hand over to the human the proposed PLAN section 2 rows (claims `<LITERATURE ID>, claim n`, each `verified` or `assumed`) and the candidate hypotheses for section 8. **Stop and wait for the human's approval.** Only then does the PLAN change, and the PLAN's `LITERATURE drawn on` line lists the artifact id. After the PLAN change the human re-confirms Approval in PLAN section 11.
8. The PLAN cites the LITERATURE by id and claim number. The LITERATURE never cites the PLAN's results.
