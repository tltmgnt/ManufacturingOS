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
