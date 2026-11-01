# ManufacturingOS

An advisory manufacturing planning system. The reference specifications in this repository describe MADMS; this implementation includes the **Phase 1 deterministic orchestration prototype** and an initial **Phase 2 serial-route calculation model**.

## Install and use the unified CLI

Python 3.11+ is required. From a source checkout:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install .
manufacturing-os --version
manufacturing-os --help
manufacturing-os study examples/integrated-study.json --output study-report.json
manufacturing-os review study-report.json --output study-review.html
manufacturing-os bundle create examples/integrated-study.json --output study-bundle.zip
manufacturing-os bundle verify study-bundle.zip
```

On Windows, activate with `.venv\Scripts\activate` instead. Commands are `plan`, `estimate`, `experiment`, `simulate`, `study`, `review`, `compare`, `bundle`, `evidence`, `sources`, `capture`, `notes`, `replicate`, `observations`, `campaign`, `campaign-bundle`, and `schema`; each supports `--help` and preserves its component's arguments and exit codes. `python -m manufacturing_os.cli` provides the same router. Existing module commands below continue to work, including the original `python -m manufacturing_os INPUT` planning interface.

The package has no third-party runtime dependencies. Building from source uses setuptools and wheel; pip may fetch build tools in its isolated build environment. To install a downloaded CI wheel offline, use `python -m pip install --no-index --no-deps PATH_TO_WHEEL.whl`. Input examples remain in the source checkout and are not installed as package data; pass your own JSON paths when running elsewhere. The versioned prototype is not published to PyPI by this workflow.

CI builds a wheel, installs it in a fresh virtual environment, and runs the complete study/review/comparison/bundle workflow outside the source checkout. Wheels and synthetic bundles are available as workflow artifacts. Local distribution validation can be run with:

```sh
python -m pip wheel --no-deps --wheel-dir dist .
python tests/smoke_installed.py dist/manufacturingos-0.1.0-py3-none-any.whl
```

## Run

Python 3.11+; no third-party dependencies, credentials, or network services required.

```sh
python -m manufacturing_os examples/synthetic-cnc.json
python -m unittest discover -s tests -v
```

The CLI writes a new JSON audit record under `runs/` (or `--output-dir`). Exit codes: `0` for a completed PASS/CONDITIONAL evaluation, `1` for FAIL, `2` for malformed input or an I/O error. A zero exit code is not approval. Invalid input is rejected before agent execution and is not persisted as a valid run.

## Implemented scope

- Versioned input, evidence, agent-result, and plan dataclasses; strict JSON input parsing, positive finite quantities with explicit units, stable identities, source revisions, UTC evidence timestamps, and referential integrity.
- A0 orchestration over a checked dependency DAG; deterministic A1–A9 mock interfaces; A10 verification. Exceptions become recorded failed results.
- Content fingerprints pin the entire input package and exact upstream result revisions. `invalidate` marks affected results STALE and propagates downstream. Re-running the orchestrator recomputes all agents; incremental caching and automatic retries are not implemented.
- Hard-constraint failures produce blocking conflict records. Unknown constraints, missing evidence, and mock outputs keep verification CONDITIONAL. Mock results never establish manufacturing feasibility.
- Append-only UUID run records contain exact inputs, evidence, DAG, results, assumptions, unknowns, verification, versions, state history, and pending human approvals. Deterministic plan content excludes run UUIDs/timestamps.

Every specialist output is explicitly unknown (`null`) with an explanatory issue. The prototype does not calculate routes, material properties, sourcing scores, capacity, cost, yield, or FMEA scores. Constraint satisfaction is supplied by the synthetic fixture, not independently established. Unit labels are preserved; conversions and controlled unit vocabularies belong to future validated calculation models. The verifier supports constraint conflicts, not arbitrary semantic contradiction detection.

No approval API, equipment control, purchase orders, enterprise integration, or production release is implemented. Human approval remains pending in every generated plan. JSON records are for local development, not a tamper-proof enterprise audit store. Use synthetic or specifically authorized input only.

## Contracts and extension points

See [data-contracts.md](data-contracts.md), [architecture.md](architecture.md), [agent-specifications.md](agent-specifications.md), [workflow-and-state-machine.md](workflow-and-state-machine.md), and [risk-and-safety.md](risk-and-safety.md). `examples/synthetic-cnc.json` is the concrete v1 input contract. Unknown constraint values require an issue. The `Agent` protocol is the extension point for deterministic test doubles; real specialist conclusions are rejected in this phase until a validated verifier and evidence rules are implemented.

Tests cover malformed inputs, reproducibility, DAG execution, upstream invalidation, hard constraints, evidence integrity, agent failures, CLI behavior, and audit reconstruction. They validate software behavior on synthetic fixtures, not manufacturing models or the full future scenario set in [verification-and-validation.md](verification-and-validation.md).

## Phase 2: bounded calculation model

```sh
python -m manufacturing_os.calculations examples/serial-route.json
python -m manufacturing_os.calculations examples/serial-route.json --variants examples/serial-route-variants.json
```

These commands emit JSON estimates to stdout. Exit `0` means the calculation completed, including when capacity is insufficient; inspect `capacity_feasible`. Invalid scenarios exit `2`. Each estimate records the model version, normalized-input fingerprint, scenario revision, source reference, explicit units, assumptions, and `UNVALIDATED_ESTIMATE` status. Sensitivity compares complete versioned scenarios and reports absolute unit-cost differences in the same currency. The Phase 1 orchestrator remains mock-based; these estimates cannot promote its approval state.

The model handles a user-supplied serial process route with parallel identical machines at each operation. Durations convert explicitly between seconds, minutes, and hours. Rates use a single declared currency; exchange conversion is unsupported. Yield and availability are fractions in `(0, 1]`. Quantities are expected values, so fractional starts are deliberate. Every operation incurs one setup per machine per horizon. Labor is dedicated per machine and billed for setup and processing only.

For target good quantity `D`, operation cycle time `t_i`, setup time `s_i`, machine count `m_i`, availability `a_i`, horizon `H`, and downstream cumulative yield `Y_i` (including operation i):

- Required input at operation i: `D / Y_i`.
- Required machine hours: `(D / Y_i) * t_i + m_i * s_i`.
- Available machine hours: `H * m_i * a_i`.
- Good-output capacity: `max(0, H * m_i * a_i - m_i * s_i) / t_i * Y_i`.
- Route capacity is the minimum operation capacity. Feasibility requires every operation's load to fit available hours.
- Total cost is entry material cost plus each operation's required machine hours times its combined machine and labor rate.

The hand-calculated synthetic reference uses 72 good units, 90% cut yield and 80% finish yield. It requires 100 entry starts and 90 finishing inputs. Material costs $500, cutting $165, and finishing $150: total $815 and unit cost $815/72. Finishing limits expected capacity to 76.8 good units per horizon. Tests also cover a doubled-demand ramp, yield degradation, multiple machines, setup overload, equivalent time units, invalid inputs, and reproducibility.

This is steady-state capacity arithmetic, not a schedule or discrete-event simulation. It excludes pipeline fill/drain, rework, queues, transfer times, shared resources, supplier disruptions, inventory, taxes, and overhead. The synthetic reference checks arithmetic only. Calibration against authorized facility datasets, empirical uncertainty bounds, and validated operational models remain outstanding Phase 2 work.

## Phase 2: exploratory simulation and reference reports

```sh
python -m manufacturing_os.experiments simulate examples/uncertainty-experiment.json
python -m manufacturing_os.experiments validate examples/arithmetic-references.json
# Optional: save a complete report to a new file (parent directory must exist).
python -m manufacturing_os.experiments validate examples/arithmetic-references.json --output reference-report.json
```

The simulation samples independent uniform ranges for operation cycle/setup times, availability, yield, and machine/labor rates. Range values use the baseline field's declared unit. All unsampled fields stay fixed. Every endpoint is validated before sampling. One to 10,000 samples and an explicit 32-bit nonnegative integer seed are required. A local Python random generator avoids changing global RNG state; supported runtimes use a sorted parameter order. The report records exact inputs, sampled parameter values, per-sample fingerprints and metrics, bottleneck counts, feasible-sample counts/fraction, and min/mean/p05/p50/p95/max summaries. Quantiles use linear interpolation at `(n-1)*p`. Re-running the same input reproduces the report; sample values are retained for inspection.

These are exploratory sampled outcomes under assumed ranges, not calibrated risk probabilities or confidence intervals. Uniformity and independence need empirical justification before any operational use. This remains steady-state uncertainty propagation, not discrete-event simulation. Reports retain the baseline assumptions and `production_authorized: false`.

The reference validator compares numeric model outputs against explicitly versioned expected values with matching units and nonnegative absolute tolerances. It emits per-check residuals and PASS/FAIL, check counts, case objectives, source references, software/model versions, input fingerprints, and the full reference suite for reconstruction. Reviewer remains `null` until a separate human review occurs. Exit codes are `0` for completed simulation or passing references, `1` for failed reference checks, and `2` for malformed input or I/O errors. `--output` exclusively creates a new report and rejects an existing path.

The supplied suite contains two independently hand-calculated synthetic cases and 12 numeric checks: the $815 baseline and a finish-yield reduction to 50% ($1,295 total cost, 160 entry starts, 48 expected good units of capacity per horizon). Passing this suite establishes arithmetic agreement only. It does not calibrate or validate the model against real manufacturing data. Authorized facility reference datasets and empirical uncertainty calibration remain outstanding.

## Phase 2: finite-batch event simulation

```sh
python -m manufacturing_os.simulation examples/finite-batch.json
python -m manufacturing_os.simulation examples/finite-batch.json --output finite-batch-report.json
```

This discrete-event scheduler models a finite batch released at time zero through the supplied serial route, with identical dedicated parallel machines per operation, FIFO queues, unlimited intermediate buffers, one setup per machine, and independent Bernoulli quality checks at completion. Setup begins at zero on every machine. Availability stretches setup and cycle durations by `1/availability`; this is an effective-rate approximation, not a breakdown or shift calendar. Machine ID breaks machine ties, and job ID breaks simultaneous arrival ties. A local seeded RNG draws in operation/FIFO job order. Scrap leaves the route immediately at operation completion.

The report includes every scheduled job-operation (arrival, queue wait, start, finish, machine, quality outcome), per-job horizon state, eventual completion/scrap time, and per-operation queue and occupancy summaries. Jobs completing exactly at the horizon count as complete. Jobs that will scrap later remain WIP until their scrap time. The batch-completion metric is the time at which every released job has either finished or scrapped. It includes events beyond the reporting horizon and is not a delivery guarantee. A target is met only when enough final good jobs have completed by the horizon.

`occupied_fraction_by_machine` includes setup and processing clipped to the reporting horizon. `peak_queued_by_horizon` counts waiting jobs after instantaneous dispatch at each event time. `mean_full_batch_queue_wait` includes the full scheduled batch, including waits after the horizon; it is zero when an operation receives no jobs. Full timelines preserve future quality outcomes separately from horizon counts. The original input, its fingerprint, simulator version, assumptions, and `UNVALIDATED_SIMULATION` status are retained for reproducibility.

A hand-calculated three-job fixture has one-hour cutting and two-hour finishing, no setup, full availability, and perfect yield. Cutting finishes at hours 1, 2, 3; finishing at 3, 5, 7. At hour 5, two jobs are good and one remains WIP. Tests cover this fixture, parallel machines, setup delays, queue waits, availability scaling, scrap removal, future-scrap horizon accounting, flow conservation, machine non-overlap, equivalent units, reconstruction, input limits, and CLI no-overwrite behavior.

Simulation is bounded to 10,000 initial jobs, 100,000 job-operations, and 10,000 total machines. Invalid input or I/O errors exit `2`; successful simulation exits `0` even if the target is missed. The model excludes transfer times, shared labor/resources, rework, finite buffers, shifts, maintenance calendars, and costs. It does not replace the separate steady-state economic model. Synthetic schedule tests check implementation behavior; real facility calibration and validation remain outstanding.

## Integrated revision-bound study

```sh
python -m manufacturing_os.study examples/integrated-study.json
python -m manufacturing_os.study examples/integrated-study.json --output study-report.json
```

A study collects the Phase 1 mock plan, steady-state estimate, finite-batch simulation, uncertainty experiment, and optional synthetic reference report in one reconstructable JSON record. All model components receive the same scenario. Simulation configuration contains only `seed` and `batch_size`; uncertainty configuration contains only `seed`, `samples`, and `ranges`. They cannot override the bound scenario.

The study contract includes an explicit binding to the manufacturing input fingerprint and normalized scenario fingerprint. If either changes, execution rejects the stale binding before analysis. After reviewing the changed inputs, callers can explicitly compute a new binding with `manufacturing_os.study.binding(package_dict, scenario_dict)`. This content binding records an association; it does not prove that the supplied process route or assumptions accurately represent the product. Qualified reviewers must establish that correspondence. Study demand must use `piece` and equal the scenario's integer good-unit target; calendar demand conversion is deliberately left to the caller.

The reference suite may be `null`. When supplied, at least one reference case must cover the exact normalized study scenario; an unrelated passing suite is rejected. Missing references and unvalidated/mock components remain explicit review findings. Plan verification failures, model capacity shortfalls, simulated target misses, or failed reference checks produce `REVISION_REQUIRED`. Otherwise the study ends at `HUMAN_REVIEW`, with approvals pending and `production_authorized: false`. The original plan verification result and conflicts remain intact; modeled shortfalls are separately labeled with their component and assumptions.

Every report stores the original study input, component versions/fingerprints, all component outputs, review findings, and required approval roles. Re-running its `input` reconstructs the deterministic report. Optional output uses exclusive creation, preserving existing files. Exit codes are `0` for a completed study needing human review, `1` for revision-required findings, and `2` for invalid/stale input or I/O errors. A zero exit code grants no release authority.

The integrated synthetic example binds 72 pieces of demand to the serial-route scenario, runs the 100-job seed-42 simulation and 100 uncertainty samples, and checks the 12 synthetic reference metrics. This connects the existing modules without replacing mock specialist conclusions, granting approvals, or adding enterprise/equipment interfaces. Real facility calibration remains outstanding.

## Offline HTML review export

```sh
python -m manufacturing_os.study examples/integrated-study.json --output study-report.json
python -m manufacturing_os.review study-report.json --output study-review.html
```

Open the HTML file in a browser for a responsive, printable review summary. Blocking findings come first, followed by study identity, cost and capacity with units, finite-horizon good/scrap/WIP and queue counts, assumed uncertainty ranges and sampled percentiles, reference residuals, original plan findings/conflicts, mock specialist issues, pending approval roles, evidence sources, assumptions, versions, and content fingerprints. Displayed measurements use six significant digits; keep the source JSON for exact numbers, full timelines, and per-sample records.

Before rendering, the exporter re-runs the saved study input and compares the entire report content against reconstruction. Altered results or a model-version mismatch are rejected; regenerate the source report using the matching implementation. Reproducibility is not a cryptographic signature, approval, or validation of source claims. The exact study input is included in a collapsible provenance section.

All input text is escaped. Source references remain plain text, and the HTML uses no scripts, forms, external fonts, images, or network resources. Internal section links aid navigation. A content security policy restricts resources to the embedded styles. The exporter preserves existing output files and exits `2` on invalid, stale, non-reproducible, or unwritable input/output. A completed export exits `0`, including reports that require revision. The export provides no approval actions or production authorization.

## Compare study revisions

```sh
python -m manufacturing_os.study examples/integrated-study.json --output before.json
python -m manufacturing_os.study examples/integrated-study-revised.json --output after.json
python -m manufacturing_os.compare before.json after.json --output comparison.json
```

The comparison reconstructs both full study reports before use and requires the same product ID. It records exact input changes as JSON Pointer paths (escaping `~` and `/`), distinguishing absent fields from explicit `null`. Input arrays retain positional ordering; operation result rows are matched by stable operation ID, with additions/removals listed separately. The report also shows changed specialist revisions, before/after plan verification, and findings introduced, retained, changed, or no longer reported.

Numeric result deltas cover cost, yield, starts/scrap, capacity, finite-batch good/scrap/WIP, completion time, and per-operation load/utilization. Deltas are computed only when unit labels match; currency conversion is never inferred. Changes to demand, horizon, facility, currency, simulation seed/batch size, uncertainty configuration, and reference suite are called out as context. Every delta is descriptive. It does not establish causality, statistical significance, improvement, or manufacturing approval. A finding no longer reported is not proof the underlying issue was resolved.

Both source study inputs, revisions, fingerprints, and report-content hashes are retained so the comparison can be reproduced with `compare_studies(run_study(before_input), run_study(after_input))`. Full event timelines and sample outputs remain in the source study JSON files. The revised example adds a second finishing machine: steady-state good-output capacity changes from 76.8 to 108 pieces per horizon. Its synthetic reference suite is explicitly absent until corresponding checks are supplied.

A completed comparison exits `0` regardless of whether either source needs revision. Invalid, stale, altered, cross-product, or unwritable comparisons exit `2`. Output creation is exclusive. The shared reconstruction check is also used by HTML export; approval remains pending in all comparison reports.

## Portable review bundles

```sh
python -m manufacturing_os.bundle create examples/integrated-study.json --output study-bundle.zip
python -m manufacturing_os.bundle verify study-bundle.zip
# Include a comparison against an existing complete study report:
python -m manufacturing_os.bundle create examples/integrated-study-revised.json --before before.json --output revised-bundle.zip
```

Creation runs the study and packages `study-input.json`, `study-report.json`, `study-review.html`, `README.txt`, and `manifest.json` into one ZIP. An optional prior report adds `previous-study-report.json` and `comparison.json`. Open the HTML review after extracting with your normal archive tool; retain the JSON for exact metrics and audit records. The manifest lists SHA-256 hashes and byte sizes of every content file; it does not hash itself.

The verifier never extracts files. It checks the archive's allowed file set, rejects duplicate paths, directories, symlinks, unsupported/encrypted entries, and oversized content, then reconstructs every expected file from the bundled study input and optional prior report. Reports with altered metrics fail even if their manifest checksums have been updated. Verification requires the matching model/export implementation and is content consistency checking, not a signature, source validation, or human approval. The bundle's input can itself be replaced by a different coherent study; authenticity must be established separately.

ZIP entry order, timestamps, and permissions are fixed for reproducible builds within the same Python/compression stack. Verification compares uncompressed contents, so compression metadata does not need to match. Limits are 64 MiB compressed and 128 MiB total uncompressed. The complete bundle is generated before exclusive output creation; existing files are preserved, and a failed output write removes its partial file. Parent directories must exist.

Create and verify exit `0` when packaging/content checks complete, including for a study requiring revision. Inspect the reported `review_state`; neither command changes approval state. Invalid inputs, corrupt/mismatched archives, limits, and I/O errors exit `2`. CI builds and verifies a synthetic bundle on each supported Python version and uploads it as a downloadable workflow artifact.

## Evidence metadata policies

```sh
manufacturing-os evidence examples/evidence-input.json examples/evidence-policy.json
manufacturing-os study examples/evidence-study.json --output evidence-study-report.json
manufacturing-os review evidence-study-report.json --output evidence-study-review.html
manufacturing-os bundle create examples/evidence-study.json --output evidence-study-bundle.zip
```

Evidence checks are opt-in through a study's `evidence_policy` field; existing studies retain their previous output when that field is absent. The standalone command accepts a ManufacturingInput and policy. Each policy declares its ID/revision, a timezone-aware UTC `as_of`, nonnegative maximum capture age in `day`, a boolean requirement for declared SHA-256 hashes, and exact pinned source URI/owner/revision/type tuples. Source URIs must be unique in the policy. No URI is fetched.

Records captured after `as_of`, older than the configured age limit, or with unpinned/mismatched source metadata are excluded from eligible coverage. A record exactly at the age limit is accepted. Supplied content hashes must be raw 64-character hexadecimal SHA-256 strings; required but absent hashes exclude the record. A well-formed hash is labeled `DECLARED_NOT_VERIFIED`: no source bytes or identity have been checked. Capture age describes the record timestamp, not the age of its underlying content.

Every requirement must have at least one eligible record naming its ID. Reports show `COVERAGE_GAPS`, `COVERED_WITH_EXCLUSIONS`, or `METADATA_CHECKS_PASSED`, with record-level issues, ages, hash status, requirement coverage, and policy/input fingerprints. Naming a claim is metadata coverage, not proof the claim is true or the requirement is substantively verified. Pinned source owners remain declared identities; these checks do not authenticate them.

Coverage gaps create a blocking study finding and `REVISION_REQUIRED`. Excluded extra records with otherwise complete coverage create a review finding. All policy-enabled studies retain an explicit metadata-only limitation and pending human approval. HTML reviews show policy checks; comparisons flag policy changes; bundles retain and reconstruct the results. UTC `as_of` is part of the input, so runs remain deterministic and do not silently depend on the wall clock.

The standalone command exits `0` for complete coverage (including excluded extra records), `1` for coverage gaps, and `2` for invalid input/policy or I/O errors. Optional output creation is exclusive. The examples are synthetic; no enterprise connector, substantive evidence verifier, or approval authority is added.

## Captured source-content verification

```sh
manufacturing-os sources examples/source-input.json examples/source-snapshot.json
manufacturing-os study examples/source-study.json --output source-study-report.json
manufacturing-os bundle create examples/source-study.json --output source-study-bundle.zip
```

The source snapshot contract contains a schema version, snapshot ID/revision, the exact ManufacturingInput fingerprint, and a list of evidence IDs with canonical base64-encoded captured bytes. It is bounded to 1,000 files and 16 MiB total decoded content. Unknown/duplicate IDs, stale input bindings, malformed or noncanonical base64, and resource-limit violations are rejected. Empty binary content is supported. Source URIs remain labels; no source URI or path is opened, fetched, or executed.

For each input evidence record, the verifier compares captured-byte SHA-256 with the declared raw 64-character hexadecimal hash (case-insensitive). Reports distinguish `HASH_MATCHED`, `HASH_MISMATCH`, missing captured content, and missing/invalid declared hashes. They retain source revisions, expected/actual hashes, byte counts, snapshot/input fingerprints, and per-requirement hash-matched coverage. Complete coverage with unmatched extra records is labeled `CAPTURED_CONTENT_COVERED_WITH_EXCLUSIONS`.

A study can opt in with `evidence_snapshot`, which requires `evidence_policy`. Combined eligible coverage is the intersection of metadata-eligible and hash-matched evidence IDs for each requirement. The same record must meet both checks; fresh metadata on one record cannot be combined with matching bytes on another stale record. Combined gaps produce `EVIDENCE_SOURCE_GAPS` and `REVISION_REQUIRED`. Missing source snapshots preserve existing study behavior. Hash matches do not override freshness, pinned metadata, hard constraints, or pending approvals.

The exact supplied source bytes remain base64-encoded in the study input and therefore travel with the JSON report, HTML provenance input, and bundle. They are not rendered or interpreted as documents. Verification checks supplied-byte consistency with supplied declarations; it does not authenticate origin, prove claim truth, or establish manufacturing conformance. Source content and policy results are separate components in the HTML report, and comparisons flag snapshot changes.

The standalone command exits `0` when every requirement has hash-matched coverage (including excluded extras), `1` for content coverage gaps, and `2` for invalid/stale inputs or I/O errors. Optional output creation is exclusive. The installed-wheel smoke test covers the new command; CI also builds, verifies, and uploads a synthetic source-backed review bundle.

## Capture selected local source files

```sh
manufacturing-os capture examples/source-input.json examples/capture-manifest.json --root examples/source-files --output captured-snapshot.json
manufacturing-os sources examples/source-input.json captured-snapshot.json
```

The capture manifest declares its schema version, snapshot ID/revision, and explicit evidence-ID/relative-path selections. The command reads only those selected files under the caller's required `--root`; it does not scan directories, infer paths from source URIs, or modify the input package or declared hashes. The output is the same source snapshot contract consumed by `sources` and an integrated study's `evidence_snapshot`. Retain the capture manifest separately if the original local path mapping is needed.

Paths must be canonical relative POSIX paths: no absolute/drive paths, traversal, backslashes, `.` aliases, or duplicate selections. Files are opened using descriptor-relative, no-follow operations rooted at the selected directory; symlink components and non-regular files are rejected. Nonblocking opens prevent FIFOs from hanging capture. Source size, identity, and modification/change timestamps are compared on the same descriptor before/after reading, and changes during capture are rejected. The selected root is resolved once, then held open for the capture. The existing 1,000-file/16-MiB limits apply cumulatively.

Secure capture requires POSIX `dir_fd`, `O_NOFOLLOW`, `O_DIRECTORY`, and `O_NONBLOCK` support. It fails explicitly on unsupported platforms rather than falling back to weaker path handling. Existing snapshot verification, studies, exports, and bundles remain portable; Windows users can consume snapshots produced in a supported environment.

All selections are validated and captured before output creation. Existing snapshot output is preserved. The command emits a summary and exits `0` for complete hash coverage, `1` when capture succeeded but declared-hash coverage is incomplete, and `2` for invalid input, unsupported platform, path restrictions, changed files, resource limits, or I/O errors. An exit-1 snapshot is retained for inspection; expected hashes are never silently replaced. Capturing bytes does not authenticate the source or approve any manufacturing claim.

## Revision-bound reviewer feedback

```sh
manufacturing-os study examples/source-study.json --output annotated-study.json
manufacturing-os notes check annotated-study.json examples/review-notes.json
manufacturing-os review annotated-study.json --notes examples/review-notes.json --output annotated-review.html
manufacturing-os bundle create examples/source-study.json --notes examples/review-notes.json --output annotated-bundle.zip
```

Create or append a note using an exact study report:

```sh
manufacturing-os notes add annotated-study.json --note-id note-1 --reviewer "Synthetic reviewer" --role quality --timestamp 2026-11-01T00:00:00Z --disposition COMMENT --comment "Review calibration assumptions" --finding-code UNVALIDATED_MODELS --output notes-v1.json
manufacturing-os notes add annotated-study.json --notes notes-v1.json --note-id note-2 --reviewer "Synthetic reviewer" --role quality --timestamp 2026-11-01T01:00:00Z --disposition REQUEST_REVISION --comment "Provide facility reference data" --output notes-v2.json
```

Each log binds to the study fingerprint and entire reconstructed report's content hash. Different study revisions or altered report content reject stale notes. Logs have their own ID and positive integer revision; appending creates a new revision without modifying the input log. Output files are exclusively created. A log supports up to 1,000 unique note IDs and 10,000 characters per comment. Timestamps must be chronological, timezone-aware UTC. Roles must match the study's required approval roles, and optional finding codes must name an integrated study finding.

Dispositions are `COMMENT`, `REQUEST_REVISION`, and `READY_FOR_FORMAL_REVIEW`. Names, roles, timestamps, and statements are supplied declarations, not authenticated identities or signatures. Readiness does not approve a plan. Every request for revision remains recorded against that exact report; later comments/readiness notes cannot erase it. Revised studies require a newly bound log. Formal approval remains outside this annotation workflow.

Assessments distinguish `NOTES_RECORDED` and `REQUESTED_CHANGES`, list request IDs and roles with/without notes, and retain pending approvals and `production_authorized: false`. HTML exports show the feedback after study findings. Bundles optionally carry `review-notes.json` and `review-notes-assessment.json`, reconstruct their contents, and report `notes_state` separately from the original study `review_state`. Neither the plan nor study output is modified by annotations. Existing note-free bundles retain their prior contents.

The notes command exits `0` for comments/readiness only, `1` if any revision request is recorded, and `2` for invalid/stale notes or I/O errors. Exit-1 logs are still saved for review. HTML/bundle generation can succeed for a report with requested changes; inspect `notes_state`. CI and the installed-wheel smoke test exercise annotations, export, and bundle verification.

## Scheduled machine downtime

```sh
manufacturing-os simulate examples/finite-batch-downtime.json --output downtime-simulation.json
manufacturing-os bundle create examples/downtime-study.json --output downtime-study.zip
```

Finite-batch inputs optionally accept `downtime`, a list of machine calendars. Each row identifies an `operation_id`, zero-based integer `machine_id`, and nonempty `windows` list. Each window has explicit duration-style `start`/`end` quantities in `s`, `min`, or `h`, measured from simulation time zero. Starts are nonnegative, ends must be later, and windows for one machine may touch but not overlap. Duplicate machine calendars and unknown operations/machines are rejected. Window order is normalized for reporting.

Downtime intervals are half-open: work may finish exactly when downtime begins and start exactly when it ends. Setup and each processing cycle are nonpreemptive and must fit entirely outside downtime. Setup takes the first suitable slot from zero; processing takes the earliest feasible slot on any parallel machine, with machine ID breaking ties. Downtime never counts as occupied setup/processing time. Queues, WIP, good output, and batch completion reflect the scheduled windows, including windows extending beyond the reporting horizon.

Calendar operations must have `availability=1` to prevent double-counting downtime through both a calendar and an effective-rate factor. Operations without calendars retain their existing availability behavior. There are at most 1,000 machine calendars and 1,000 total windows. Calendar runs additionally require `batch_size * (total machines + total windows) <= 1,000,000`, bounding candidate-slot search work.

Integrated studies accept the same calendar under `simulation.downtime`; HTML shows normalized intervals and comparisons flag the changed simulation configuration. Scheduled windows affect only the finite-batch model: the steady-state economic/capacity and uncertainty models exclude them, with an explicit `DOWNTIME_SCOPE` review finding. The example's maintenance window causes a simulated target miss and a revision-required study; packaging/verification still succeeds while retaining that state.

Reports retain normalized calendars and per-machine setup intervals for inspection. No-calendar inputs preserve their previous output. This remains an unvalidated simulator: calendars are supplied assumptions, not live equipment schedules, and no recurring shifts, random failures, shared resources, or equipment commands are implemented.

## Full simulated batch economics

```sh
manufacturing-os simulate examples/finite-batch-costs.json --output batch-costs.json
manufacturing-os bundle create examples/cost-study.json --output cost-study.zip
```

Set `include_costs: true` on a finite-batch input (or `simulation.include_costs` in a study) to add `cost_report`. The flag must be boolean. Absent/false leaves costing disabled. Calendar setup intervals remain controlled by the separate optional `downtime` field.

The full-batch model charges every released piece for entry material. Each operation charges nominal processing hours for the actual jobs reaching it, plus one planned setup per configured machine, even if that machine or downstream operation receives no jobs. Machine and dedicated labor costs use the scenario's supplied hourly rates. Queueing, idle periods, scheduled downtime, and availability duration-stretching add no billable active hours. These are explicit model assumptions, not universal accounting rules.

Costs include the entire released batch and all future simulated operations, including events beyond the reporting horizon. Unit cost divides total batch cost by eventual good output, not good units at the horizon or the requested target. If no good units finish, `unit_cost` is `null` with an explanatory issue and declared unit; it is never zero-filled. Material, machine, labor, total, and per-operation costs retain units and a versioned `full-batch-active-cost-1.0` model identifier.

A hand-calculated three-job reference charges $15 material, $90 cutting, and $120 finishing: total $225 and $75 per eventual good unit. At hour five only two jobs are good, while the third finishes at hour seven; the full-batch denominator remains three. Tests also check planned parallel-machine setups, upstream scrap reducing downstream work, zero rates, no-good-output cases, and downtime/availability not adding idle-hour charges.

These costs are separate from steady-state expected-value estimates. Studies retain an explicit `FULL_BATCH_COST_SCOPE` finding, and undefined unit cost gets its own finding. HTML shows component costs and assumptions. Comparisons add full-batch deltas only when both studies enable costing, preserve undefined values, and require matching units/currencies. No overhead, tax, rework, overtime, inventory valuation, quoted pricing, or margin model is included. Estimates remain unvalidated and grant no production approval.

No-cost inputs retain their previous report and bundle contents. CI and the installed-wheel smoke test exercise cost-enabled simulation, while CI publishes a synthetic cost-review bundle.

## Repeated seeded finite-batch simulations

```sh
manufacturing-os replicate examples/replication-experiment.json --output repeated-runs.json
manufacturing-os replicate examples/replication-experiment.json --replay 0 --output first-run.json
manufacturing-os bundle create examples/replication-study.json --output repeated-study.zip
```

Replication experiments contain a schema version, experiment ID/revision, `runs`, and one complete `simulation` template. Routes, parameters, calendars, batch size, and costing stay fixed; only the seed changes. Run index `i` uses `(template_seed + i) modulo 2**32`, with a separate local RNG per simulation. Every outcome records its index, seed, input fingerprint, full-report hash, target attainment, horizon good/scrap/WIP, eventual output, batch completion, and optional full-batch costs. Replay returns the full original simulation and timelines for an index.

Summaries report min, mean, p05, median, p95, and max with units, plus defined/undefined run counts. Quantiles use linear interpolation at `(n-1)*p`. Unit costs from no-good-output runs remain `null`; statistics include only defined values and are unavailable when all runs are undefined. Total batch costs remain defined, even when no good output completes. Full-batch cost scope includes events beyond the reporting horizon.

The target-met fraction describes these seeded model outcomes. It is not a calibrated manufacturing probability, measured service level, or confidence interval. Unlike the independent-uniform input uncertainty experiment, replications do not vary the configured parameters. Both depend on unvalidated model assumptions and need empirical calibration before operational use.

Studies can opt in with `replications: {"runs": 20}`. The report uses the exact study simulation template; run zero reproduces its baseline simulation. Findings retain replication scope, sampled target misses, and undefined unit costs. HTML shows defined-value summaries and counts, comparisons flag replication configuration changes, and bundles reconstruct all outcomes. Source timelines are replayable instead of duplicated into every outcome row. Studies without replications retain their previous output.

Experiments allow 1 to 1,000 runs. Aggregate scheduling work is limited to `runs * (batch_size * operation_count + total_machines) <= 2,000,000`; calendar work additionally requires `runs * batch_size * (total_machines + window_count) <= 2,000,000`. The existing per-simulation limits also apply. This bounds repeated work before execution. Invalid inputs, indexes, limits, and I/O errors exit `2`; completed replication/replay exits `0` regardless of sampled target misses. Optional output creation is exclusive. CI and installed-wheel checks exercise replications, replay, and a downloadable synthetic study bundle.

## Captured observation reference checks

```sh
manufacturing-os study examples/observation-study.json --output observation-study.json
manufacturing-os observations observation-study.json --output observation-checks.json
manufacturing-os bundle create examples/observation-study.json --output observation-review.zip
```

An optional study `observation_checks` selects an evidence ID and absolute tolerances for exactly the metrics declared by a captured JSON reference. It requires metadata policy, captured sources, and replications. The selected record itself must be metadata-eligible and hash-matched; unrelated eligible records cannot make it available. Source JSON is parsed only after those checks and must follow the strict observation-reference contract. Duplicate JSON keys are rejected.

Reference content declares its schema version, kind (`synthetic` or `declared_observations`), positive observation count, context, and numeric unit-bearing metrics. Context must match product/design revision, facility/revision, normalized scenario fingerprint, simulation-configuration fingerprint, batch size, and horizon. These declarations associate the data with the analysis case; they do not authenticate its origin. The readable `examples/observation-reference.json` is the exact source content captured inside the example study.

Checks compare replication means against declared observed values with analyst-supplied nonnegative absolute tolerances. Supported metrics are horizon good/scrap/WIP, eventual good/scrap, batch completion time, full-batch total cost, and full-batch unit cost. Metric units must match exactly; horizon context supports explicit time conversion. A model metric absent from the run or undefined in any replication fails explicitly, rather than comparing a conditional mean that silently excludes no-good-output runs.

The report records reference ID/source/revision/kind/count, context, observed values, model means, signed residuals, tolerances, and per-check PASS/FAIL. Selected-source failure yields `REFERENCE_UNAVAILABLE`; a valid source from another case yields `CONTEXT_MISMATCH`. Those outcomes and failed numeric checks require study revision. Passing reference checks never overrides a simulated target miss, hard constraint, other blocking finding, or pending approval.

The first fixture is independently hand-calculated synthetic arithmetic: three released pieces, one-hour cutting, two-hour finishing, perfect yield, and a five-hour horizon. Two pieces are good by the horizon and the third completes at hour seven. Total batch cost is $225, or $75 per eventual good unit. The study requests two good pieces; tests separately confirm that requesting three remains revision-required despite matching all six reference metrics.

These checks evaluate agreement, not model fitting, facility calibration, statistical confidence, source truth, or generalization. `declared_observations` is a supplied label, not an authorization or authenticity certificate. Real reference data and tolerances need qualified review. HTML and bundles retain results/provenance, comparisons flag changed check configuration, and studies without this feature retain prior output. The observations command first reconstructs the complete study report, then exits `0` for PASS, `1` for failed/unavailable/mismatched references, and `2` for invalid/stale input or I/O errors. Output creation is exclusive. CI and installed-wheel checks exercise the command and a synthetic downloadable reference-review bundle.

## Bounded multi-study scenario campaigns

```sh
manufacturing-os campaign examples/scenario-campaign.json --output campaign-report.json
```

A campaign embeds complete study inputs and explicitly declares each case's expected review state, exact blocking-finding codes, and expected observation-check status (`null` when that feature is absent). Cases run sequentially and independently. The runner retains full inputs, completed study reports and hashes, actual/expected states, field-level mismatches, and child execution errors. Invalid child studies fail their case and do not silently skip later cases; execution errors cannot be configured as an expected pass.

Campaign `PASS` means the configured software expectations matched. It does not mean the studies are ready, calibrated, authenticated, or approved. The synthetic four-case example passes its software expectations while retaining three revision-required studies: an undersized batch, a numeric reference disagreement, and stale evidence. Its first case checks the hand-calculated reference successfully. Summary fields separately show expectation pass/fail counts, execution errors, and revision-required studies; production authorization remains false.

Campaigns support 1 to 20 unique case IDs, 32 MiB of embedded JSON input, and 128 MiB of full output. Preflight aggregates estimated scheduling work (baseline plus replications, including calendar candidate work) and uncertainty-model work, capped at 2,000,000 units, with at most 10,000 total uncertainty samples. Underlying per-study limits still apply. Malformed studies are recorded as case errors when execution is within the campaign's structural/resource limits. No source URI/path scanning or extra source retrieval occurs; captured bytes remain in their explicit study inputs.

Reports use compact sorted JSON to bound size and retain exact data. Re-running `run_campaign(report["input"])` reconstructs the deterministic campaign. `--output` exclusively creates a new file and prints a compact summary; without it, stdout contains the full report. Exit codes are `0` when every case matches, `1` for expectation mismatches or child execution errors, and `2` for invalid campaign structure, aggregate limits, or I/O errors. No file is created until the campaign finishes and output limits are checked. Existing output is preserved. CI and the isolated installed-wheel workflow exercise the example, and CI uploads the full synthetic campaign report.

## Portable campaign review bundles

```sh
manufacturing-os campaign-bundle create examples/scenario-campaign.json --output campaign-review.zip
manufacturing-os campaign-bundle verify campaign-review.zip
```

Open `campaign-review.html` after extracting the bundle with your normal archive tool. Its offline overview shows expectation results separately from actual study states, highlights revision-required studies and execution errors, and links to each case's full HTML review and JSON report. Case labels are escaped text; paths use fixed numeric indexes such as `cases/001/study-review.html`, never user-supplied case IDs. Cases that failed to execute have `error.json` instead of a fabricated study report.

The ZIP includes `campaign-input.json`, `campaign-report.json`, `campaign-review.html`, `README.txt`, a checksum/size manifest, and indexed per-case files. The overview uses no scripts, forms, external fonts/images, or network resources. Full study inputs and captured bytes travel with the JSON records. The campaign report is reconstructed before overview rendering, and each completed study is reconstructed before its review is exported.

Verification does not extract files. It bounds file count and compressed/uncompressed size, enforces known root/indexed names, rejects duplicate paths, directories, non-regular file metadata, encryption, and unsupported compression, then reconstructs every expected file from the campaign input. Both campaign and existing study bundle verifiers reject special device/FIFO/socket metadata in addition to symlinks. Checksums alone cannot hide edited reports with an unchanged input, but content consistency is not a signature, source authentication, model calibration, or formal approval.

ZIP order/timestamps/permissions are fixed for reproducible builds within the same runtime/compression stack; verification compares uncompressed content, not compression metadata. Limits are 64 MiB compressed and 128 MiB total uncompressed, plus the campaign's own input/work limits. Per-case JSON/HTML duplicates some campaign-report content, so a campaign that fits its standalone report limit can still be too large for a review bundle. All files are generated before exclusive archive output; existing output is preserved.

Create/verify exit `0` when packaging/content reconstruction succeeds, including campaigns whose software expectations failed. Inspect `campaign_status`, `revision_required_studies`, and `execution_errors`; successful packaging never changes those states or grants approval. Invalid input, corrupt/mismatched content, limits, and I/O errors exit `2`. CI and installed-wheel checks build and verify the synthetic campaign and upload the complete review ZIP.

## Strict JSON ingestion

All CLI JSON file inputs and embedded archive/reference JSON now use one bounded reader. Duplicate keys are rejected at every object depth, even if both values are identical. `NaN`, `Infinity`, `-Infinity`, and float literals overflowing to infinity are rejected before schema/model evaluation. Nesting is limited to 128 container levels, with deeper/parser-overflow input rejected rather than producing a traceback. Standard integer/float semantics and clean-input serialization remain unchanged; this is not an arbitrary-precision numerical format.

Files must be UTF-8, with an optional UTF-8 BOM; UTF-16/32 is not silently autodetected. Configuration/input files default to 32 MiB, while full-report consumers use 128 MiB. Embedded archive payloads remain subject to archive limits as well as strict JSON parsing. Inputs are stat-checked, opened as regular files, read with a byte bound, and checked on the same descriptor for size/identity/mtime/ctime changes. Directories/FIFOs and files changing during reads fail explicitly. An explicitly selected regular-file symlink is allowed here; the separate source-capture root still enforces its stricter no-symlink policy.

These checks do not authenticate files or make metadata tamper-proof. They prevent ambiguous field selection, non-finite JSON values, unbounded JSON reads, and accidental mixed-file revisions within the documented checks. Invalid input returns the existing command error code `2` before new output is created. Model contracts, units, approvals, report serialization, and valid existing study/bundle contents remain unchanged.

## Exportable core JSON Schemas

```sh
manufacturing-os schema list
manufacturing-os schema export input --output manufacturing-input.schema.json
manufacturing-os schema export scenario --output scenario.schema.json
manufacturing-os schema validate input examples/evidence-input.json
manufacturing-os schema validate scenario examples/serial-route.json
```

The two v1.0 core contracts (`ManufacturingInput` and serial-route `Scenario`) ship as JSON Schema Draft 2020-12 documents inside the wheel. Their stable URN identifiers and internal-only `$ref` definitions support editor associations and external structural validators without adding runtime dependencies or fetching remote references. Configure schema associations in the editor/tool; adding a `$schema` property to an actual input is not supported by the runtime's exact-field contract.

`schema validate` uses the existing authoritative runtime parsers, not a partial reimplementation or a generic JSON Schema engine. It performs strict JSON ingestion plus model checks without starting agents, simulations, or a study. A `VALID` result means the input contract is satisfied only; even a correctly represented hard-constraint violation can be valid input, and no production authorization is granted.

The exported schemas describe structure, required/unknown fields, ordinary ranges, unit shapes, and constraint issue/null rules. They cannot replace every semantic check. Runtime validation additionally enforces entity-ID uniqueness, evidence claim references, timezone-aware UTC timestamps, exact integer representation, and rate units matching the root currency. JSON Schema considers `1.0` an integer mathematically, while runtime count fields require an actual JSON integer. Those boundaries are documented and tested explicitly.

Export output is exclusively created; existing files are preserved. List/export/valid input exit `0`; unknown contracts, invalid semantic/JSON input, missing packaged assets, and I/O errors exit `2`. Each export reads a fresh packaged document, so callers cannot mutate shared schema state.

Local standard-library tests exercise export and authoritative validation. CI additionally installs the development-only validator from `requirements-schema-tests.txt`, checks both documents against the Draft 2020-12 metaschema, validates positive/negative structural fixtures, and demonstrates the documented semantic boundaries. To reproduce that independent check:

```sh
python -m pip install -r requirements-schema-tests.txt
python tests/check_exported_schemas.py
```

The validator is not a runtime requirement. The isolated wheel test confirms the JSON assets are included and that export/validation work without it.

## Study input preflight without analysis

```sh
manufacturing-os schema validate study examples/observation-study.json
```

Study preflight checks the exact input contract, version/content bindings, demand/target agreement, simulation options/calendars/resource limits, uncertainty ranges/endpoints, replication settings/budgets, reference-suite structure and scenario coverage, evidence policy, captured bytes, and optional observation-reference contract/context. It does not run agents, create random generators, schedule jobs, calculate cost/capacity, compare model results to references, or generate study outputs. `analysis_executed` remains `false`.

The `VALID` result means input preflight completed, not that a plan is feasible or ready. Evidence freshness/content gaps and unavailable/mismatched observation references remain explicit diagnostic statuses, including combined metadata-and-content coverage gaps. A reference can be structurally valid even when its numeric values will disagree with the model; those comparisons are deliberately not evaluated. Model arithmetic, seeded outcomes, readiness, and approvals still require the actual study/review workflow.

Execution now uses the same preparation/validation path before analysis, catching late configuration errors before simulations allocate timelines or run samples. Metadata/content checks are reused by execution. Successful study serialization and existing valid bundle contents remain unchanged; malformed inputs can surface errors earlier. The command uses strict JSON ingestion and exits `2` for malformed contracts/bindings/options. It writes no run files. There is no exported structural study schema yet: `schema export` remains limited to the two core schemas, while `schema validate study` performs authoritative runtime preflight.
