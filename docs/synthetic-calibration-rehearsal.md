# Synthetic fitting and held-out evaluation rehearsal

This is a software rehearsal of the [calibration protocol](calibration-protocol.md),
not empirical calibration. It uses three deliberately simple synthetic fitting
records and one separate synthetic held-out batch. All metrics, seeds, baseline
and tolerances are preselected for the toy case. No statistical generalization,
real source authorization or production approval is claimed.

Run from the repository root:

```sh
python -m examples.synthetic_calibration_rehearsal --output runs/calibration-rehearsal
```

The runner reads only bundled fixtures, makes no network requests, and refuses an
existing output directory. It is a repository example, not an installed CLI command.
Partial output may remain on a failed run; choose a fresh directory for reruns.

## Ordered workflow

1. Read `synthetic-fitting-records.csv`: three distinct fitting batches each supply
   one finishing-cycle measurement in hours. All three values are 2 hours.
2. Estimate the finishing cycle time using their arithmetic mean. Freeze the
   candidate, fitting file hash, batch IDs, method and six metric criteria into a
   fingerprinted record before reading the held-out export. The fixed absolute
   tolerance is 1e-9 in each metric's declared unit; it is for deterministic toy
   arithmetic, not an appropriate default for manufacturing measurements.
3. Read the separate `synthetic-batch-export.csv`. Reject any held-out batch ID
   appearing in the fitting set. Recompute and check the candidate fingerprint
   before evaluation; changing a parameter or criterion invalidates it.
4. Evaluate the fixed baseline (2.5-hour finish cycle) and frozen candidate
   (2-hour finish cycle) against the same held-out observed values. Each reference
   is bound to its analysis context; rebinding does not change observed values.
5. Retain all residuals, raw files, frozen configuration, inputs, reports, HTML
   reviews, verified bundles and the rehearsal summary. Do not refit after looking
   at held-out errors. A new fit would require new untouched validation data.

| Held-out outcome | Baseline | Frozen candidate | Synthetic observation |
| --- | --- | --- | --- |
| Good brackets by hour 5 | 1 | 2 | 2 |
| Batch completion | 8.5 h | 7 h | 7 h |
| Full-batch processing cost | 255 USD | 225 USD | 225 USD |
| Cost residual | +30 USD | 0 USD | — |
| Reference outcome | FAIL | PASS | — |
| Review state | REVISION_REQUIRED | HUMAN_REVIEW | — |

A candidate PASS does not complete calibration, prove generalization or grant
production authorization. The tiny noiseless fixture is intentionally easy.
Tests alter held-out cost and require a candidate FAIL without altering its frozen
parameter; this checks that held-out values do not drive fitting.

## Review artifacts and limits

CI runs the rehearsal across Python 3.11–3.13 and uploads the entire directory as
`synthetic-calibration-rehearsal-python-VERSION`. Open each case's
`study-review.html` and inspect `rehearsal-summary.json` for the paired residuals.

Retain the whole directory: individual study ZIPs contain held-out source evidence
but do not include the separate fitting CSV/frozen-candidate records. Hashes and
fingerprints establish consistency, not an authenticated lock time, identity or
independent source truth. Different batch IDs alone do not prove independence;
source overlap and temporal dependence require qualified review with real data.

The actual calibration milestone still requires approved facility records,
representative measurement definitions, sufficient data, independently justified
thresholds, uncertainty treatment, untouched validation and qualified acceptance.
