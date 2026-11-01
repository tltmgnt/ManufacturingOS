# ManufacturingOS

An advisory manufacturing planning system. The reference specifications in this repository describe MADMS; this implementation is the **Phase 1 deterministic orchestration prototype**.

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
