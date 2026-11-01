# Complete offline synthetic suite

Run every current offline rehearsal with one command from the source checkout:

```sh
python -m examples.offline_suite --output runs/offline-suite
```

Open `runs/offline-suite/index.html`. No real enterprise/facility source, real
credentials or external network access is used. The existing mock API runs only
on loopback; local source/Git metadata is captured for traceability.

| Component directory | Coverage |
| --- | --- |
| `repeatability/` | Two complete pilot runs, independently verified and compared across 72 retained files |
| `repeatability/first/` and `second/` | Planning alternatives, CSV/mock API intake, rejected access/transport faults, fitting/held-out evaluation and eight study bundles per run |
| `edges/` | Six hand-derived scheduling/cost edge cases, including target misses and undefined unit cost |
| `invariants/` | 54 fixed configurations, 162 simulations and conservation/cost/replay/horizon checks |

`offline-suite.json` records component results and captured source fingerprints.
All components must retain the same source fingerprint for overall PASS. Exit 0
means all software checks pass; exit 1 means a completed mismatch/failure; exit 2
means input/execution failure. A failed component leaves its phase and available
partial outputs, without publishing an overall successful page/scorecard.
Use a fresh directory outside captured source roots; existing output is preserved.

The component commands remain available. This wrapper is a repository example,
not an installed runtime CLI command, and adds no third-party runtime dependency.
Individual pilot directories retain their own verifiable file manifests. The
suite root is an overview, not a new signed or authenticated bundle format.

## CI and browser review

One `offline-suite` job replaces the three separate offline jobs and uploads
`offline-synthetic-suite`. Download/extract it and open its top-level `index.html`.
Prior artifacts remain under their original names in earlier runs.

The separate Chromium job checks the new overview and existing reviews at mobile,
tablet and desktop widths. Its `synthetic-demo-browser-review` artifact includes
16 screenshots. Screenshots are stored at the suite root, outside both paired
pilot runs; the browser job re-verifies the pair remains byte-repeatable afterward.

Software PASS is not production approval, measured accuracy, calibrated
probability, real enterprise integration or shadow-pilot acceptance. The three
real-world milestones remain open. This suite allows continued offline work
without substituting synthetic results for those milestones.
