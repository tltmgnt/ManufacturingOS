# Offline synthetic repeatability rehearsal

Continue development without any real facility/enterprise read:

```sh
python -m examples.offline_repeatability --output runs/offline-repeatability
```

The command runs the complete synthetic pilot twice using bundled local fixtures.
Mock HTTP is bound only to loopback and uses ephemeral mock credentials; no external
ERP/MES, real credentials or facility dataset is used. This repository example
requires a source checkout and has no third-party runtime dependencies.

Both child runs must pass the full rehearsal verifier before comparison. The
comparison covers every retained file plus each manifest, including source and
environment metadata, reports, fitting records, audits, HTML and ZIP bytes. The
current workflow compares 72 files per run. Random mock tokens are not retained.

- Exit 0 / REPEATABLE: all compared bytes match in this environment.
- Exit 1 / MISMATCH: both runs verify, but their retained files differ; inspect the
  listed paths and first/second byte sizes and hashes in `repeatability.json`.
- Exit 2: a run or verification failed. Available partial files and a FAILED phase
  remain in `run-status.json`; an incomplete pair does not publish a successful
  repeatability result.

Choose a new output directory outside captured source roots, normally under
`runs/`. Existing output is preserved. Open `first/index.html` and
`second/index.html` to inspect results. Each child retains its independent manifest
and full provenance. CI uploads the pair as `offline-synthetic-repeatability`.

Exact repeatability in one environment does not establish empirical accuracy,
independent source truth, cross-platform byte equality, availability guarantees,
real calibration, enterprise acceptance or an actual shadow pilot. Environment or
source differences can legitimately produce a mismatch; no such differences are
silently normalized away.
