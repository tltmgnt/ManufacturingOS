# Bounded shadow-pilot plan

Status: UNFILLED — no actual pilot or empirical outcome has been recorded.
Prepare this plan before evaluation. It supports the third milestone in the
[pilot overview](pilot-milestones.md), not production control or release.

## Entry record and frozen scope

- Pilot ID/revision; accountable owner; participating facility/product family:
- Calibration scope/decision reference and applicable model limitations:
- Read-only integration/security scope and decision reference:
- Software commit/tag, source fingerprint, environment and configuration:
- Product/design, route/facility revisions and applicable operating regime:
- Evaluation interval, observational unit and sampling/eligibility rules:
- Baseline process, measurement source and comparable baseline interval:
- Engineering, quality, cybersecurity and management reviewers:

Record actual organizational entry decisions. A synthetic software PASS or a
reference agreement check is not a substitute for those decisions.

## Predeclared evaluation measures

| Measure | Definition/denominator and units | Baseline source and matching rule | Acceptance rule/owner | Missing/undefined treatment |
| --- | --- | --- | --- | --- |
| Horizon throughput/target misses | To be defined | To be supplied | To be decided before evaluation | To be defined |
| Completion-time prediction error | To be defined | To be supplied | To be decided before evaluation | To be defined |
| Good/scrap/WIP agreement | To be defined | To be supplied | To be decided before evaluation | To be defined |
| Full-batch cost error/accounting scope | To be defined | To be supplied | To be decided before evaluation | To be defined |
| Review burden and decision comprehension | To be defined | To be supplied | To be decided before evaluation | To be defined |
| Source/availability and recovery failures | To be defined | To be supplied | To be decided before evaluation | To be defined |

Select relevant measures rather than implying all are required in every pilot.
Record sample sufficiency, dependence, uncertainty handling and regime changes.
Compare like-for-like batches and definitions. Do not discard failed/no-good
batches, substitute conditional means for undefined outcomes or tune acceptance
thresholds after seeing results. A revised plan requires a new recorded revision
and disposition of data already examined.

## Operating procedure and stop rules

The system runs alongside the existing process. Outputs go to qualified review;
production continues through the existing authorized workflow. No automatic
write-back, purchase, engineering change, machine command or production release
is part of this plan.

Define who pauses evaluation for unauthorized/stale/partial data, revision or
unit mismatches, unsupported model regimes, unexpected unsafe recommendations,
unexplained residuals, audit gaps, security incidents or lost reviewer coverage.
Record the manual fallback, incident owner, containment, investigation and restart
criteria. These rules need actual owner review before a real pilot begins.

## Per-case record

- Case/batch ID and selection/exclusion decision:
- Raw source/revision/hashes and transformation lineage:
- Frozen model/configuration, input binding, seeds and source fingerprint:
- Predicted/observed values, residuals, undefined values and target outcomes:
- Source/model/reviewer failures and manual disposition:
- Review record, actual decision and any departure from the plan:

Retain all eligible cases and reported failures. Supplied reviewer roles and note
hashes do not authenticate the reviewer; link the actual organizational record.

## Exit package

Aggregate the predeclared measures with counts, uncertainty, missing outcomes,
all exceptions, failures, scope limits and unresolved actions. Include the baseline
comparison and human-factors findings. Use the [acceptance record](pilot-acceptance-record.md)
to index the evidence and qualified decision. A decision applies only to its
recorded advisory scope; operational expansion is a separate authorization.
