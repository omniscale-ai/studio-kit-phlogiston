---
description: Fixture for design_gate tests: three simulator batches, seven experiments.
status: draft
---

# DATASET — design gate fixture

**ID**: `cpt-enz-dataset-fixture`

## 6. Acquisition

| Batch | Phase | Origin | Experiments | Justification (type → target) | Design method | Simulator preview | Actual duration | Approved by |
|-------|-------|--------|-------------|-------------------------------|---------------|-------------------|-----------------|-------------|
| 1 | PRE-1 | simulator | e1, e2, e3 | `variance → Km_A` | propose_doe_experiments, D-optimal, seed 1 | n/a | 5 min | Test Person, 2026-10-01 |
| 2 | CYCLE-1 | simulator | e4, e5 | e4: `information → cpt-enz-comparison-c1 pair H1/H2`; e5: `variance → Km_B` | propose_doe_experiments, T-optimal H1 vs H2, seed 2 | n/a | 3 min | Test Person, 2026-10-01 |
| 3 | CYCLE-2 | simulator | e6, e7 | `boundary → temperature range of cpt-enz-hypothesis-arrhenius` | manual: the design tool has no temperature-boundary criterion | n/a | 1 min | Test Person, 2026-10-01 |

## 8. Known Defects

None.
