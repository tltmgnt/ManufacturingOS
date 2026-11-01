# First-facility calibration protocol

Status: preparation only. No facility dataset has been supplied, no parameters
have been fitted, and no empirical acceptance claim has been established.
The bundled observation examples are synthetic software checks.

Use [the intake worksheet](calibration-intake.md) to scope one product family,
facility, route, and operating regime before collecting or comparing data.
Keep actual exports and completed sensitive worksheets in the approved data
location; this public repository is not the default destination for them.

## 1. Authorize and define the dataset

Record the data owner's permission, allowed use, retention, access restrictions,
export revision, collection interval and timezone. Record the source system,
extraction query/version, original file hashes, and all transformations. Remove
unneeded personal/customer identifiers under the owner's requirements. Hashes
establish byte consistency; permission and source authenticity need separate
organizational records.

Select completed batches with traceable product, design, facility and route
revisions. Retain failures, scrap, interruptions and incomplete batches in the
intake inventory. Document exclusions before fitting, including their counts and
reasons. Do not silently discard inconvenient observations or reinterpret missing
values as zero. Incomplete batches cannot supply full-batch completion or cost.

Required raw records depend on the metrics selected:

| Record | Required meaning |
| --- | --- |
| Batch | Stable batch ID, starts, product/design, route/facility revisions, start/end timestamps |
| Operation | Operation and machine IDs, setup and processing intervals, quantities in/good/scrap, rework flags |
| Calendar | Shift and downtime intervals, timezone, planned/unplanned classification |
| Counts | Good, scrap and WIP at the specified horizon; final disposition when available |
| Costs | Currency, accounting period, material per start, machine/labor rates, charged hours and included overhead |

Check duplicate IDs, timestamp order, overlapping events, counter reconciliation,
units and revision consistency. Preserve a transformation/exclusion log so each
aggregate can be traced back to its source rows. Do not manufacture timestamps or
sample sizes to satisfy the software contract.

## 2. Establish whether the model applies

The current simulator represents a bounded serial route with FIFO scheduling,
identical parallel machines per operation and Bernoulli scrap. Check the actual
route for rework, alternate routing, shared operators/tools, transport, blocking,
maintenance dependencies and dispatching rules. Record each unsupported behavior
and its expected effect. If it materially changes the selected metrics, stop and
extend or replace the model before making an empirical claim.

Define batch time origin, horizon, completion event and WIP membership explicitly.
Full-batch cost includes starts and processing beyond the horizon; align the
accounting scope before comparing it. Do not compare horizon-only recorded costs
with full-batch simulated costs. Undefined unit costs remain undefined.

## 3. Freeze the evaluation design before fitting

Split by whole batch (or a larger independent production group), never by rows
from the same batch. Reserve a later time period or distinct production groups
for validation; record how temporal dependence and regime changes are handled.
Prevent fitting/validation leakage through shared aggregates or derived rates.

Record fitting and held-out batch IDs, dataset hashes, metrics, units, tolerances,
minimum evidence requirements, baseline, replication count and seeds. A qualified
owner must choose numeric criteria for this facility; none are provided by the
synthetic example. Include a documented rule for uncertainty, sample dependence,
small samples and missing outcomes. The existing comparator supplies absolute
residual checks, not confidence intervals or a statistical acceptance procedure.

Estimate cycle/setup times, yields and cost parameters from fitting records only.
Retain baseline values, fitted values, estimation method, fit diagnostics and
parameter plausibility review. The software has no automatic fitting command.
Lock the candidate parameters and study revision before examining held-out errors.
If validation drives further tuning, that set becomes fitting data: obtain a new
untouched validation set and record the iteration.

## 4. Build revision-bound references

Use `examples/observation-reference.json` as a structural example only. For real
records, `reference_kind` is `declared_observations`; that label does not certify
authenticity. Declare the number of actual observational units and the aggregation
method in the intake record. Simulation replications are not observed batches.
For replicated model means, use an explicitly justified comparable observed
aggregate. A single batch and a population mean are not interchangeable.

Each reference context binds product/design, facility/revision, batch size,
horizon, scenario fingerprint and simulation-config fingerprint. Normalize the
scenario through the existing study preparation path before deriving its binding;
use `manufacturing_os.models.digest` for the simulation configuration. Fingerprints
identify the analysis context, not an independently measured ground truth. Preserve
the original export separately from the derived reference JSON and its hashes.

Different batch sizes, horizons or operating regimes require separate compatible
studies; do not pool incompatible cases into one reference. Changing scenario or
simulation configuration requires a new bound reference revision, retaining the
underlying observed values and the derivation history.

Add the reference as evidence, pin its metadata in `evidence_policy`, capture its
exact bytes in `evidence_snapshot`, and select it in `observation_checks`. Set
unit-bearing absolute tolerances for exactly the reference metrics. Finalize
source hashes before calculating input bindings and capturing the snapshot.
Use the manifest-based `capture` command for explicitly selected local files on a
supported POSIX system. Never replace a declared hash merely to suppress a mismatch.
See the README sections on evidence policies, capture and observation checks.

## 5. Execute and retain evidence

For a completed, locally authorized `facility-study.json`:

```sh
python -m manufacturing_os.cli schema validate study facility-study.json
python -m manufacturing_os.cli study facility-study.json --output facility-report.json
python -m manufacturing_os.cli observations facility-report.json --output facility-checks.json
python -m manufacturing_os.cli review facility-report.json --output facility-review.html
python -m manufacturing_os.cli bundle create facility-study.json --output facility-review.zip
python -m manufacturing_os.cli bundle verify facility-review.zip
```

Use new output paths for every revision. Preflight only checks contracts; it does
not run simulations or establish agreement. The observation command exits 0 for
PASS, 1 for a completed non-PASS result and 2 for invalid input or execution errors.
Retain and investigate every non-PASS result rather than hiding it with changed
tolerances. Bundle verification establishes reconstructable content, not source
authenticity, calibration acceptance or manufacturing authorization.

Retain software tag/commit, environment, original exports and hashes, transforms,
intake record, study inputs, seeds, reports, bundles, baseline/candidate comparisons,
all residuals and the review decision. Keep fitting and held-out results distinct.

## 6. Close the milestone with a qualified decision

A completed package must state supported regimes, exclusions, residuals against
predeclared criteria, uncertainty limitations, model discrepancies, failed cases,
and the disposition of each failure. Engineering and data owners review the
measurement definitions and fit; quality reviews the evaluation criteria and
recorded outcome. Record actual organizational decisions in the approved system.
Repository reviewer notes contain self-declared identities and are not signatures.

The calibration milestone remains open until authorized real data, a frozen
candidate, untouched validation results and qualified acceptance evidence exist.
Agreement with synthetic data or one reference is insufficient. Calibration alone
does not complete enterprise integration, shadow-pilot acceptance, or authorize
production use.
