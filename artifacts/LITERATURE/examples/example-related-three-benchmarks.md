---
description: Worked example (Path 1, related work, literature mode allowed) on "Three Benchmarks Addressing Open Challenges in Nonlinear System Identification": 36 papers in the set, 2 claims (1 verified, 1 assumed), gate PASS offline and online (with `--plan`), 46 of 84 OpenAlex credits used.
status: verified
---

# LITERATURE — related: Three Benchmarks Addressing Open Challenges in Nonlinear System Identification

**ID**: `cpt-ctank-literature-example-related-three-benchmarks`

<!-- toc -->

- [1. Request](#1-request)
- [2. Sources](#2-sources)
- [3. Set](#3-set)
- [4. Collection](#4-collection)
- [5. Analysis](#5-analysis)
- [6. Claims](#6-claims)
- [7. Candidate Hypotheses](#7-candidate-hypotheses)
- [8. Attestation](#8-attestation)

<!-- /toc -->

## 1. Request

- PLAN: `cpt-ctank-plan-example`
- Literature mode: `allowed`, copied from the PLAN's section 2.
- Exclusions checked: not applicable.
- Strategy: `related`
- Anchor: https://doi.org/10.1016/j.ifacol.2017.08.071
- Bounds: no year bound.
- Depth: quick
- Output shape: reading list.
- Cost stated before running: OpenAlex only, ≤ 84 credits.
- Cost used: 46 OpenAlex credits of the 84 stated: 14 for retrieval (5 requests; 934 remaining that day) and 32 for the online gate's DOI lookups (32 work lookups, 1 credit each; section 8).

## 2. Sources

| source | ran | query or tool calls | budget used | note |
|--------|-----|---------------------|-------------|------|
| OpenAlex | yes | https://api.openalex.org/works/https://doi.org/10.1016/j.ifacol.2017.08.071?select=id%2Cdoi%2Ctitle%2Cpublication_year%2Ctype%2Ccited_by_count%2Cprimary_location%2Cauthorships%2Ctopics%2Cabstract_inverted_index%2Creferenced_works%2Crelated_works%2Cbest_oa_location | 14 credits | 5 requests; keyless |
| Consensus | not configured | — | 0 | set CONSENSUS_API_KEY to enable |
| Hypothesis | not configured | — | — | set HYPOTHESIS_MCP_KEY and build a collection of the approved set |

- Removed by exclusion: not applicable.

## 3. Set

| # | DOI | year | title | role | cited by | resolved | OA link |
|---|-----|------|-------|------|----------|----------|---------|
| 1 | 10.1061/jmcea3.0002106 | 1976 | Method for Random Vibration of Hysteretic Systems | reference | 2674 | yes |  |
| 2 | — | 1976 | METHOD FOR RANDOM VIBRATION OF HYSTERETIC SYSTEMS. | reference | 1096 | no DOI |  |
| 3 | 10.1007/s11831-009-9031-8 | 2009 | The Hysteresis Bouc-Wen Model, a Survey | reference | 743 | yes |  |
| 4 | — | 2013 | Nonlinear System Identification: NARMAX Methods in the Time, Frequency, and Spatio-Temporal Domains | reference | 655 | no DOI | http://ci.nii.ac.jp/ncid/BB14138754 |
| 5 | 10.1016/j.automatica.2010.10.013 | 2010 | System identification of nonlinear state-space models | reference | 566 | yes | http://urn.kb.se/resolve?urn=urn:nbn:se:liu:diva-65958 |
| 6 | 10.1016/b978-0-12-093270-2.x5048-x | 1998 | Hysteresis in magnetism : for physicists, materials scientists, and engineers | reference | 491 | yes |  |
| 7 | 10.1016/j.automatica.2012.09.018 | 2012 | Identification of Hammerstein–Wiener models | reference | 297 | yes | http://urn.kb.se/resolve?urn=urn:nbn:se:liu:diva-89528 |
| 8 | 10.1016/j.automatica.2010.01.001 | 2010 | Identification of nonlinear systems using Polynomial Nonlinear State Space models | reference | 279 | yes |  |
| 9 | — | 2007 | Systems with Hysteresis: Analysis, Identification and Control Using the Bouc-Wen Model | reference | 245 | no DOI |  |
| 10 | 10.1016/j.automatica.2008.02.016 | 2008 | Maximum likelihood identification of Wiener models | reference | 189 | yes |  |
| 11 | 10.2514/3.45199 | 1985 | The influence of laminar separation and transition on low Reynolds number airfoil hysteresis | reference | 161 | yes |  |
| 12 | 10.3182/20080706-5-kr-1001.00457 | 2008 | Maximum Likelihood Identification of Wiener Models | reference | 137 | yes | http://urn.kb.se/resolve?urn=urn:nbn:se:liu:diva-56063 |
| 13 | 10.1145/3567591 | 2022 | Constructing Neural Network Based Models for Simulating Dynamical Systems | citer | 136 | yes | https://www.osti.gov/servlets/purl/1988410 |
| 14 | 10.1016/j.automatica.2021.109666 | 2021 | Learning nonlinear state–space models using autoencoders | citer | 125 | yes |  |
| 15 | 10.1016/j.earscirev.2019.102965 | 2019 | The Cyclostratigraphy Intercomparison Project (CIP): consistency, merits and pitfalls | citer | 97 | yes | https://www.sciencedirect.com/science/article/pii/S0012825219304179/pdf |
| 16 | 10.1016/j.ejcon.2021.01.008 | 2021 | Continuous-time system identification with neural networks: Model structures and fitting criteria | citer | 80 | yes | https://www.sciencedirect.com/science/article/pii/S0947358021000169/pdf |
| 17 | 10.1016/j.engappai.2023.106226 | 2023 | Model Predictive Control when utilizing LSTM as dynamic models | citer | 65 | yes |  |
| 18 | 10.1109/cdc.2018.8619475 | 2018 | Learning Nonlinear State-Space Models Using Deep Autoencoders | citer | 44 | yes |  |
| 19 | 10.3390/computation5040047 | 2017 | Nonlinear-Adaptive Mathematical System Identification | citer | 41 | yes | https://www.mdpi.com/2079-3197/5/4/47/pdf?version=1512047136 |
| 20 | 10.4121/12960104 | 2020 | Cascaded Tanks Benchmark Combining Soft and Hard Nonlinearities | citer | 38 | yes | https://research.tue.nl/en/datasets/154df25d-425b-4178-9e12-a45df07f6a37 |
| 21 | 10.1016/j.automatica.2021.109686 | 2021 | Kernel-based methods for Volterra series identification | citer | 37 | yes | https://zenodo.org/record/6580646 |
| 22 | 10.3390/app11114972 | 2021 | Comparing Methods of DC Motor Control for UUVs | citer | 34 | yes | https://www.mdpi.com/2076-3417/11/11/4972/pdf?version=1622455087 |
| 23 | 10.1186/s40323-025-00291-9 | 2025 | Response estimation and system identification of dynamical systems via physics-informed neural networks | citer | 33 | yes | https://amses-journal.springeropen.com/counter/pdf/10.1186/s40323-025-00291-9 |
| 24 | 10.1109/lcsys.2021.3135835 | 2021 | Multiple Shooting for Training Neural Differential Equations on Time Series | citer | 28 | yes | https://arxiv.org/pdf/2109.06786 |
| 25 | 10.1007/978-0-387-68630-1 | 2007 | Adaptive Nonlinear System Identification: The Volterra and Wiener Model Approaches | related | 138 | yes |  |
| 26 | 10.1016/j.enconman.2003.08.005 | 2003 | Nonlinear modeling and identification of a DC motor for bidirectional operation with real time experiments | related | 165 | yes |  |
| 27 | 10.1016/j.ymssp.2011.06.010 | 2011 | Nonlinear modeling and identification of a spark ignition engine torque | related | 50 | yes |  |
| 28 | 10.1109/cca.2003.1223261 | 2004 | Experimental nonlinear identification of a two mass system | related | 25 | yes |  |
| 29 | 10.1109/sice.2008.4655117 | 2008 | Identification of Wiener-type nonlinear systems by using M-sequence correlation method | related | 5 | yes |  |
| 30 | 10.1007/bf00449705 | 1996 | Selection of input variables for model identification of static nonlinear systems | related | 7 | yes |  |
| 31 | 10.1016/j.conengprac.2026.106871 | 2026 | Nonlinear system identification for a nano-drone benchmark | same-topic | 1 | yes | https://doi.org/10.1016/j.conengprac.2026.106871 |
| 32 | 10.1016/j.ifacol.2024.08.574 | 2024 | Baseline Results for Selected Nonlinear System Identification Benchmarks | same-topic | 7 | yes | https://doi.org/10.1016/j.ifacol.2024.08.574 |
| 33 | 10.48550/arxiv.2405.10779 | 2024 | Baseline Results for Selected Nonlinear System Identification Benchmarks | same-topic | 0 | yes | https://arxiv.org/pdf/2405.10779 |
| 34 | — | 2018 | An Investigation of the Wiener Approach for Nonlinear System Identification Benchmarks | same-topic | 0 | no DOI | https://eprints.lancs.ac.uk/id/eprint/124945/1/BookOfAbstracts2018_30.pdf |
| 35 | 10.2172/922532 | 2007 | Nonlinear System Identification for Damage Detection | same-topic | 117 | yes | https://www.osti.gov/servlets/purl/922532 |
| 36 | 10.1017/dce.2026.10067 | 2026 | Benchmarking for nonlinear system identification: Submission platform and baseline results | same-topic | 0 | yes | https://www.cambridge.org/core/services/aop-cambridge-core/content/view/BD06B2C87096B4A700EE173A298A0FEC/S2632673626100677a.pdf/div-class-title-benchmarking-for-nonlinear-system-identification-submission-platform-and-baseline-results-div.pdf |

- Approved by: A. Shumilov, 2026-10-12

## 4. Collection

not used

## 5. Analysis

Prior work the anchor builds on falls into three sub-problems. Hysteresis modelling: the Bouc–Wen differential model, introduced for random vibration of hysteretic systems [1], surveyed with its identifiability issues [3], is the basis of the anchor's first benchmark. Nonlinear state-space identification: polynomial nonlinear state-space models fitted from a best linear approximation [8] and the maximum-likelihood state-space approach [5] are the methods the anchor's Wiener–Hammerstein benchmark is meant to test. Block-oriented identification: maximum-likelihood Wiener identification [10] and Hammerstein–Wiener identification [7] set the baseline the anchor asks new methods to beat. What the anchor adds is not a method but three measured datasets with stated challenges, so that these methods can be compared on the same records.

## 6. Claims

| claim | set # | quote | location | status |
|-------|-------|-------|----------|--------|
| Bouc–Wen hysteresis has been surveyed with its identification difficulties | 3 | "The Hysteresis Bouc-Wen Model, a Survey" | title | verified |
| PNLSS models are initialised from the best linear approximation | 8 | — | — | assumed |

## 7. Candidate Hypotheses

none — the Set is consistent on the anchor's question.

| candidate | claims | proposed diagnostic condition | status |
|-----------|--------|-------------------------------|--------|

## 8. Attestation

- Retrieval: `python3 scripts/lit_run.py related 10.1016/j.ifacol.2017.08.071 --system ctank --out architecture/literature -n 12`, run 2026-10-12; `scripts/lit_run.py` 0.1.0, OpenAlex REST keyless (`https://api.openalex.org`), 5 requests, 14 credits.
- Set approved by A. Shumilov, 2026-10-12.
- Hand-over to `cpt-ctank-plan-example` section 2: claim 1 `verified`, claim 2 `assumed`; approved by A. Shumilov, 2026-10-12.
- Gate, offline: `python3 scripts/lit_gate.py architecture/literature/example-related-three-benchmarks.md`, run 2026-10-12: PASS; structural checks only.
- Gate, online: `python3 scripts/lit_gate.py architecture/literature/example-related-three-benchmarks.md --plan architecture/PLAN.md --resolve`, run 2026-10-12: PASS; 32 DOIs looked up in OpenAlex (32 credits), 32 resolved; 4 rows `no DOI`. Status set to `verified` on this result.
