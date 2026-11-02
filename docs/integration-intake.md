# Real read-only integration intake

Status: UNFILLED — no source selected, credentials supplied, access granted or
integration accepted. This worksheet can be prepared offline. Keep completed
sensitive records and secrets in the organization's approved location.

## Scope, ownership and source contract

- Intake ID/revision; accountable integration owner; source/data owner:
- System/product and supported API/export version; approved environment:
- Facility/product/route boundary; required objects and fields:
- Source owner's permission and allowed purpose; access/retention restrictions:
- Approved API documentation/export contract and revision:
- Allowed hosts/endpoints/object filters; prohibited operations:
- Source revision/snapshot identity and change/deletion semantics:
- Refresh frequency, freshness policy, capture time and source-event time:
- Volume, pagination, maximum file/response size and workload limits:

Use the actual selected source's contract. Do not assume its endpoints, units,
identifiers or revision behavior match the synthetic `/v1/batches/.../export` mock.

## Field mapping to the bounded model

| Target field/meaning | Source object/field | Unit/timezone/revision | Transformation and missing-value rule | Owner review reference |
| --- | --- | --- | --- | --- |
| Product/design and facility/route identity | Not supplied | Not supplied | Not supplied | Pending |
| Batch starts and horizon good/scrap/WIP | Not supplied | Not supplied | Not supplied | Pending |
| Final dispositions and completion event | Not supplied | Not supplied | Not supplied | Pending |
| Operation/machine cycle/setup/calendar | Not supplied | Not supplied | Not supplied | Pending |
| Full-batch material/machine/labor cost | Not supplied | Not supplied | Not supplied | Pending |

Distinguish measured facts from model parameters and supplied assumptions. Record
all joins, deduplication, time conversions, aggregation and exclusions. Retain raw
export hashes and transformation versions. Do not silently turn missing values
into zero or mix revisions, horizons, currencies or accounting scopes.

## Identity, access and security decisions

- Read-only service identity, owner and approved permission evidence:
- Authentication/token lifecycle, renewal/revocation and least-privilege scope:
- TLS/certificate validation and approved network boundary:
- Secret storage/injection/redaction mechanism; access and rotation owners:
- Audit records, protected storage, retention, correlation and monitoring:
- Untrusted-content handling, schema/input quotas and dependency review:
- Threat-model reference, security tests and cybersecurity decision reference:

Store secret references rather than secret values in the intake. The existing
loopback token, hash checks and self-declared identities are software rehearsals;
they do not fulfill these organizational requirements.

## Failure and recovery contract

Define behavior for unauthorized/forbidden access, throttling, timeout, interrupted
or truncated responses, stale revisions, schema/units mismatch, missing pages,
duplicates, partial exports and source changes during capture. Record whether any
retry is permitted, its idempotency rationale, bounds/backoff and visibility.
Define when cached data can be used and how its age/revision is exposed.

A rejected or incomplete source must not silently become a model-ready dataset.
Record the failure and the manual fallback. Define disable/revoke procedures,
incident owner, backup/recovery evidence and recovery acceptance criteria.

## Required handoff evidence

- Contract/mapping review and representative authorized fixtures:
- Source revision, integrity, completeness and lineage checks:
- Read-only permission and denied-operation evidence:
- Unauthorized, stale, malformed and interrupted-source test results:
- Secrets/redaction, audit, recovery and security-review results:
- Unresolved issues, scope limits, responsible owners and disposition:
- Organizational integration decision record and date:

Follow [the three-milestone overview](pilot-milestones.md) and
[existing security requirements](../risk-and-safety.md). This worksheet does not
contact a system, grant access, validate credentials or authorize production.
