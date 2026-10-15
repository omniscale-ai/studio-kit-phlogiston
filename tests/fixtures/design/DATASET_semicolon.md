---
description: Fixture for design_gate tests: targets that contain `;`, copied verbatim from the design log.
status: draft
---

# DATASET — design gate fixture, targets with `;`

**ID**: `cpt-enz-dataset-fixture-semicolon`

## 6. Acquisition

| Batch | Phase | Origin | Experiments | Justification (type → target) | Design method | Simulator preview | Actual duration | Approved by |
|-------|-------|--------|-------------|-------------------------------|---------------|-------------------|-----------------|-------------|
| 1 | PRE-1 | simulator | e8, e9 | e8: `information → C_A shape at the low end; with e9 it also gives the slope of log r0 in 1/T`; e9: `information → C_A shape at the hot end of the T range; with e8 it also gives the slope of log r0 in 1/T` | manual: two end points of the T range; the design tool has no Arrhenius criterion | n/a | 2 min | Test Person, 2026-10-02 |
| 2 | CYCLE-1 | simulator | e10, e11 | `variance → k1 at 25 °C; k2 held at its PRE-1 estimate` | propose_doe_experiments, D-optimal, seed 3 | n/a | 2 min | Test Person, 2026-10-02 |

## 8. Known Defects

None.
