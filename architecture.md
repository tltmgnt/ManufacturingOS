# System Architecture

## 1. System boundary

MADMS converts a versioned product and production definition into a proposed manufacturing plan. It is an advisory planning system. The system boundary ends at a documented release recommendation and required human approvals.

## 2. Logical components

1. **Input and context layer** — imports design metadata, BOM, requirements, facility capability, supplier data, and constraints.
2. **Orchestration layer** — creates a dependency graph, assigns tasks, tracks execution, and handles retries and conflicts.
3. **Specialist-agent layer** — performs domain-specific analysis.
4. **Shared knowledge and evidence layer** — stores source references, revisions, assumptions, units, and provenance.
5. **Digital-twin/simulation layer** — evaluates process, capacity, yield, cost, and disruption scenarios when validated models and data are available.
6. **Verification layer** — checks consistency, hard constraints, completeness, and evidence traceability.
7. **Human review layer** — routes engineering, quality, sourcing, and production decisions to authorized personnel.
8. **Audit layer** — records inputs, outputs, model/configuration versions, approvals, and changes.

## 3. Orchestration pattern

The Manufacturing Orchestrator decomposes the request into tasks and creates a directed acyclic graph (DAG) where possible. For example, DFM and preliminary material screening may begin in parallel. Final process planning may depend on geometry and material decisions. Capacity and cost estimates depend on process route, facility data, and sourcing assumptions.

Agents return structured outputs. The orchestrator does not treat an agent's natural-language assertion as verified evidence.

## 4. Decision hierarchy

- **Hard constraints:** safety, regulatory, customer, material, geometry, machine-envelope, and mandatory quality requirements.
- **Conditional constraints:** constraints that require explicit approval or additional evidence.
- **Soft objectives:** cost, throughput, utilization, lead time, and waste reduction.

Hard constraints are not traded away by a weighted objective function. Soft objectives may be optimized only inside the feasible region.

## 5. Conflict resolution

Conflicts are represented explicitly with:
- conflicting claims or values;
- source and revision for each claim;
- constraint type and severity;
- affected operations and downstream agents;
- proposed resolution options;
- required decision owner;
- final disposition and rationale.

The orchestrator may request clarification or re-run dependent agents. It cannot override a hard constraint or substitute its own authority for an authorized engineer or quality representative.

## 6. Proposed deployment topology

Initial development: local or controlled cloud environment using synthetic data.

Future pilot: isolated integration environment with read-only connectors to approved PLM, ERP, MES, QMS, and supplier systems. Write-back and machine-control interfaces are excluded from the initial scope.

## 7. Observability

Each run should record:
- run ID and timestamp;
- input package ID and revision;
- agent and model versions;
- tool and schema versions;
- agent task inputs and outputs;
- evidence references;
- retries, exceptions, and human interventions;
- verification outcomes and approval records.
