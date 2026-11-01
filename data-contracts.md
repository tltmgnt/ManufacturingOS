# Data Contracts

## 1. Contract principles

- Use stable IDs and explicit schema versions.
- Preserve units and source revisions.
- Represent unknown values as `null` plus an explanatory issue; do not fabricate values.
- Separate observed data, assumptions, estimates, and recommendations.
- Include provenance for material claims.
- Store timestamps in ISO 8601 UTC format.

## 2. Core entities

### ManufacturingInput
A versioned package containing product identity, design revision, BOM, requirements, production demand, facility context, and constraints.

### AgentResult
Contains agent ID/version, status, structured findings, assumptions, evidence references, uncertainty, open issues, and upstream dependency revisions.

### ManufacturingPlan
Contains the consolidated route, materials, suppliers, capacity, cost/yield, quality, risk, readiness, verification, and approval state.

### EvidenceRecord
Contains evidence ID, source URI or controlled reference, source owner, revision, content hash where permitted, capture timestamp, evidence type, and applicable claim IDs.

## 3. Units and measurement

Every dimensional or quantitative field must declare a unit or reference a controlled unit system. Conversion must be explicit and tested. Tolerances must preserve nominal value, upper/lower limits, and datum/reference context where relevant.
