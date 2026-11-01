# Complete temporary pilot rehearsal

This one-command rehearsal consolidates the existing synthetic workflows. It
exercises software behavior while real data and enterprise access are unavailable.
It is not an actual shadow pilot and does not close any real-world acceptance gate.

From a source checkout, using Python 3.11 or later:

```sh
python -m examples.temporary_pilot --output runs/temporary-pilot
```

Open `runs/temporary-pilot/index.html`. No network connection, service credentials
or third-party runtime packages are required. The example reads bundled fixtures
and creates a new output directory; existing output is preserved. The examples
remain repository modules rather than installed runtime CLI commands.

| Directory/file | Review purpose |
| --- | --- |
| `index.html` | Combined review and explicit open real-world milestones |
| `rehearsal-scorecard.json` | Software check results and full component summaries |
| `run-status.json` | RUNNING, COMPLETE or FAILED with component phase |
| `planning/` | Four cases: agreement, discrepancy, shortfall and assumed remedy |
| `intake/` | Synthetic raw CSV, derived reference, provenance and verified bundle |
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
