# Three remaining pilot milestones

Status: offline preparation only. No authorized facility dataset, real enterprise
connector or actual shadow pilot has been supplied or accepted in this project.
The [v0.3.0 checkpoint](https://github.com/tltmgnt/ManufacturingOS/tree/v0.3.0)
provides synthetic software evidence. It does not close the three milestones.

| Milestone | Current real-world state | Entry inputs | Closure evidence | Accountable role to assign |
| --- | --- | --- | --- | --- |
| M1 — Calibration | Authorized data not supplied; empirical acceptance pending | One product family/facility, approved raw records, measurement definitions, predeclared criteria and fitting/held-out split | Frozen candidate, untouched validation results, all residuals/exclusions/limitations and qualified decision | Engineering/data owner, with quality review |
| M2 — Read-only integration | Real source/API and service identity not selected | Approved system/environment, API/export contract, field mapping, read-only permissions and security design | Source/contract/access/audit/failure tests plus organizational cybersecurity acceptance | Integration owner and cybersecurity owner |
| M3 — Shadow pilot | Actual evaluation not started | Accepted bounded model/integration scope, baseline, evaluation plan, reviewers and stop rules | Measured matched results, exceptions/failures, generalization limits and qualified acceptance | Pilot owner, with engineering/quality/cybersecurity/management review |

Owner roles above are proposed responsibilities, not assigned people or approval
claims. The scope and actual accountable people must be recorded by the organization.
M2 design can proceed alongside M1; actual shadow evaluation requires its relevant
model and data-access prerequisites to be accepted for the selected scope.

## Handoff sequence

1. Complete the [calibration intake](calibration-intake.md) and
   [calibration protocol](calibration-protocol.md). Keep raw records, transforms,
   fitting and held-out evidence in the approved location.
2. Complete the [integration intake](integration-intake.md) before building against
   a real source. Resolve endpoint, identity, mapping, failure-handling and security
   decisions. A local mock token or fixture is not an enterprise service identity.
3. Freeze the [shadow-pilot plan](shadow-pilot-plan.md) before looking at evaluation
   outcomes. Measure performance in the agreed regime without production control.
4. Use the [acceptance record](pilot-acceptance-record.md) to index each milestone's
   evidence and the actual organizational decision. It is a template, not a fourth
   milestone, authenticated signature or automatic approval.

## Work available while remaining offline

Prepare proposed field mappings from the published source contract, measurement
and sampling definitions, acceptance-criteria proposals, threat-model questions,
reviewer workflow and stop/recovery procedures. Exercise synthetic success and
failure cases with the offline suite. Mark unsupplied inputs as unsupplied; do not
invent facility IDs, access grants, observations, reviewers or approval decisions.

## Decision boundaries

A milestone closes only when the qualified organization accepts its recorded
scope and evidence. Supplied document references and self-declared reviewer notes
do not authenticate that decision. Record actual decisions in the approved system.
Production authorization in this prototype remains false. Write-back, equipment
control and production release require the separate process in the
[existing risk and safety boundaries](../risk-and-safety.md).

Use the [metadata-only handoff preflight](pilot-readiness.md) to list missing
owner and evidence-reference fields without fetching sources or inferring acceptance.
