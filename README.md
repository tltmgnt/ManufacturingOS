# ManufacturingOS

An advisory manufacturing planning system. The reference specifications in this repository describe MADMS; this implementation includes the **Phase 1 deterministic orchestration prototype** and an initial **Phase 2 serial-route calculation model**.

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
