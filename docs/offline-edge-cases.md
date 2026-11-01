# Offline synthetic edge cases

Run a bounded scheduling/cost rehearsal without enterprise access, external
network requests, service credentials or facility data:

```sh
python -m examples.offline_edge_cases --output runs/offline-edge-cases
```

This source-checkout example uses the bundled bracket scenario and hand-derived
expectations. It records inputs, full simulation reports, exact expected/actual
metrics, differences and local source provenance. It does not change the core
simulator's contracts or claim empirical calibration.

| Case | Good by horizon | Horizon WIP | Eventual good | Completion | Full-batch cost | Unit cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 2 | 1 | 3 | 7 h | 225 USD | 75 USD/good |
| Slower finish (3 h/piece) | 1 | 2 | 3 | 10 h | 285 USD | 95 USD/good |
| Short deadline (2 h) | 0 | 3 | 3 | 7 h | 225 USD | 75 USD/good |
| Small batch (1 start) | 1 | 0 | 1 | 3 h | 75 USD | 75 USD/good |
| Seeded finishing scrap | 0 | 1 | 0 | 7 h | 225 USD | Undefined |
| Seeded upstream scrap | 0 | 0 | 0 | 3 h | 105 USD | Undefined |

All cases retain demand for two good brackets. Only the baseline meets it. The
short-deadline case retains cost after the reporting horizon. Upstream scrap
avoids downstream processing charges; entry material and cutting costs remain.
Zero eventual good output retains `unit_cost: null` plus a diagnostic, never a
fabricated zero cost.

The scrap cases use a positive yield fraction of 0.01 at one operation and seed
42. All three jobs scrap in these particular seeded realizations. This is not a
zero-yield input, a guaranteed outcome across seeds, or a calibrated probability.
The model's strictly positive yield input contract remains unchanged.

A software PASS means every declared edge expectation matched, including target
misses and undefined values. Exit 0 is PASS, exit 1 is a completed mismatch with
retained differences, and exit 2 is invalid input/execution failure. Partial
outputs may remain on failure; no completed scorecard is promised then. Use a
fresh output directory outside captured source roots. Existing outputs are
preserved. CI stores these results under `edges/` in `offline-synthetic-suite`.

No production approval, enterprise integration, real-world accuracy or actual
shadow-pilot acceptance follows from these toy cases. Full-batch costs exclude
capex, added fixed costs, overhead, taxes and rework.


Open the suite’s top-level `index.html` for all offline results. The component
command remains available independently; earlier CI runs retain their original
artifact names.
