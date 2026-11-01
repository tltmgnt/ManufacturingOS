# Offline synthetic invariant sweep

Run 54 bounded synthetic cases without enterprise access, external network calls,
credentials or facility data:

```sh
python -m examples.offline_invariant_sweep --output runs/invariant-sweep
```

The fixed grid combines seeds 0/1/42, batch sizes 1/3/10, finishing yields
0.2/0.8/1.0, and one/two finishing machines. Other bracket-scenario inputs remain
fixed. Each case runs the original input, a same-input replay, and a horizon-only
variant: 162 simulations in total. The variant's horizon is later than both the
original horizon and batch completion.

Checks cover:

- Horizon and final count conservation, nonnegative counts and disposition bounds.
- Full-batch cost reconciliation and unit cost per eventual good output.
- Undefined unit cost with a diagnostic when final good output is zero.
- Exact same-input report replay.
- Unchanged final dispositions, completion time and full-batch costs when only
  the reporting horizon extends, with all final dispositions visible afterward.
- Production authorization remaining false throughout.

The command retains original and extended-horizon reports (each includes its
input), replay/report fingerprints, per-case issues and source provenance.
`invariant-scorecard.json` reports PASS only when all checks pass. Expected target
misses and zero-good-output cases remain visible rather than being treated as
production approvals. CI uploads `offline-synthetic-invariant-sweep` for review.

Exit 0 means all software invariants passed; exit 1 means completed checks found
issues; exit 2 means input/execution failure. Existing output is preserved. Use a
new directory outside captured source roots. Partial files may remain on failure;
no completed scorecard is promised then. This is a repository example rather than
an installed runtime CLI command.

These checks establish bounded model self-consistency, not independent measured
validation, calibrated probabilities, exhaustive coverage or real-world accuracy.
The sweep does not claim that arbitrary machine/parameter changes monotonically
improve stochastic outcomes. Actual calibration and pilot acceptance remain open.
