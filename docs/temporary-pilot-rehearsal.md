# Complete temporary pilot rehearsal

This one-command rehearsal consolidates the existing synthetic workflows. It
exercises software behavior while real data and enterprise access are unavailable.
It is not an actual shadow pilot and does not close any real-world acceptance gate.

From a source checkout, using Python 3.11 or later:

```sh
python -m examples.temporary_pilot --output runs/temporary-pilot
```

Open `runs/temporary-pilot/index.html`. No external service connection, real credentials or third-party runtime packages are
required. The API component briefly starts an HTTP server bound only to
`127.0.0.1` on an automatically selected port, uses an ephemeral mock read token held only
in memory, and shuts down after one GET. The example reads bundled fixtures
and creates a new output directory; existing output is preserved. The examples
remain repository modules rather than installed runtime CLI commands.

| Directory/file | Review purpose |
| --- | --- |
| `index.html` | Combined review and explicit open real-world milestones |
| `rehearsal-scorecard.json` | Software check results and full component summaries |
| `rehearsal-manifest.json` | Exact retained-file inventory, byte sizes and hashes |
| `source-provenance.json` | Source-file hashes/fingerprint, Git context and Python/platform metadata |
| `run-status.json` | RUNNING, COMPLETE or FAILED with component phase |
| `planning/` | Four cases: agreement, discrepancy, shortfall and assumed remedy |
| `intake/` | Synthetic raw CSV, derived reference, provenance and verified bundle |
| `api/` | Local read-only mock API, transport provenance, request audit and study review |
| `api-failures/` | Nine rejected source/access/transport faults, request audits and failure review |
| `calibration/` | Fitting records, held-out export, frozen candidate, baseline/candidate residuals and reviews |

A successful command exits 0 and reports SOFTWARE_REHEARSAL_PASSED. This requires
the deliberate discrepancy and shortfall to remain detectable; not every case's
observation report passes. Production authorization, empirical calibration,
live integration and actual shadow-pilot completion remain false.

Failures exit 2. Available partial outputs and a FAILED phase remain for diagnosis;
there is no success index/scorecard when a component fails before summary creation.
Do not treat a directory's existence as success. Inspect `run-status.json` and use
a fresh directory for reruns. Keep the entire output tree: individual study ZIPs
do not contain the separate fitting provenance files.

## CI artifact

The Python 3.11–3.13 matrix runs the complete command and uploads
`synthetic-pilot-rehearsal-python-VERSION`, including available outputs on failure.
This replaces the three separate planning/intake/calibration artifacts for future
runs; prior run artifacts retain their original names. Download and extract the
artifact, then open its top-level `index.html` locally. Chromium screenshots remain
in the separate `synthetic-demo-browser-review` artifact. That job also checks
the combined page at mobile, tablet and desktop widths and saves screenshots.

After this rehearsal, real-world progress requires the facility and data-owner
inputs in the [calibration protocol](calibration-protocol.md), selected enterprise
systems and identity/access decisions, then an actual shadow-pilot evaluation.
Synthetic software PASS results do not substitute for those inputs or decisions.

## Source provenance

Each run records hashes of `.py`, `.json` and `.csv` files under `manufacturing_os/`
and `examples/`, plus `pyproject.toml`. Their sorted fingerprint is copied into
the scorecard. Python version/implementation and platform/machine are recorded
separately. Available Git commit and dirty state describe only the captured source
roots; a missing Git checkout/tool leaves those fields null, not falsely clean.

The run rechecks source hashes before writing its successful scorecard. Source
changes fail the run and retain its failed phase. Choose output outside the two
captured source directories (normally under `runs/`) so results do not become
source inputs. Snapshot files must be regular and not symlinks; per-file and total
limits are 4 MiB and 16 MiB.

This is local traceability, not signed build provenance or proof that the recorded
files are exactly the loaded interpreter code. Tests, docs and system libraries
are outside the source fingerprint. A dirty checkout needs its patch/source files
preserved separately for reproduction; hashes alone do not recover missing code.
The project version remains a release label and is not used as a substitute for
this source fingerprint.

## Verify a copied or downloaded rehearsal

From the matching source checkout:

```sh
python -m examples.rehearsal_integrity runs/temporary-pilot
```

Verification exits 0 for VERIFIED_CONTENT and 2 for missing, modified, extra or
inconsistent files. It checks the exact manifest inventory, complete/synthetic
status, source fingerprints, all eight reconstructable study ZIPs, matching loose
inputs/reports/HTML, and fitting/held-out reconstruction. It never extracts ZIPs.
Paths, symlinks, regular-file types, counts and byte sizes are bounded. Limits are
250 files/500 entries, 32 MiB per file and 128 MiB total; the manifest is limited
to 256 KiB. Do not add notes inside a verified directory without creating a new
reviewed artifact, since extra files invalidate the original inventory.

The manifest excludes itself. It is a consistency inventory, not a signature:
someone can replace files and recompute hashes. Reconstruction strengthens
internal consistency but still does not authenticate origin, reviewer identity,
organizational acceptance or production authorization. Source/environment changes
can prevent reconstruction; use the recorded matching checkout and dependencies.

CI verifies the complete matrix artifact before upload. The browser job stores screenshots outside both repeatability child directories,
then re-verifies that the paired runs remain byte-repeatable. Screenshots do not
change either child manifest or grant authenticity or authorization.

Verification also cross-checks the combined/component scorecards against the
verified study reports, source snapshots, transport bytes/audits and failure
expectations. Refreshing a manifest cannot make a conflicting target flag,
residual, request method or model-execution claim internally consistent. This
remains a supplied-content consistency check, not an authenticated assertion
that an external event happened.
