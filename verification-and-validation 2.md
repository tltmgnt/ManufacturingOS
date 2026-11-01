# Verification and Validation Plan

## 1. Purpose

Define reproducible tests for data integrity, agent contracts, constraint handling, workflow behavior, and plan consistency. This plan is a proposed test strategy; passing tests must be demonstrated by an executable implementation.

## 2. Test layers

- **Schema tests:** required fields, types, units, enumerations, and references.
- **Unit tests:** deterministic calculations and agent-specific rules.
- **Integration tests:** inter-agent contracts and dependency propagation.
- **Scenario tests:** complete synthetic manufacturing cases.
- **Adversarial tests:** missing, stale, contradictory, malformed, or manipulated inputs.
- **Regression tests:** ensure fixes do not break established behavior.
- **Human-factors tests:** reviewer comprehension, override controls, and approval clarity.

## 3. Initial acceptance targets

These are proposed engineering targets and must be calibrated to the selected pilot:

| Test area | Initial target |
|---|---|
| Schema validation | 100% of invalid fixtures rejected |
| Required provenance fields | 100% of material recommendations include source/revision or explicit `unknown` |
| Stale dependency detection | 100% of seeded stale-result cases detected |
| Hard-constraint enforcement | 100% of seeded hard-constraint violations block PASS |
| Contradiction reporting | All seeded critical contradictions surfaced |
| Reproducibility | Identical deterministic inputs produce identical deterministic outputs |
| Audit reconstruction | All designated scenario decisions reconstructable from run records |

No metric should be claimed as achieved until measured and reported with test counts and methodology.

## 4. Scenario set

1. CNC-machined component with tolerance and machine-envelope constraints.
2. Injection-molded component with tooling lead-time and draft-angle questions.
3. PCB assembly with component sourcing and inspection constraints.
4. Capacity-constrained production ramp.
5. Supplier disruption and alternate-source scenario.
6. Yield degradation and rework-cost scenario.

## 5. Verification rules

- Missing critical inputs block a PASS.
- Hard constraints cannot be traded against cost or throughput objectives.
- Estimates must expose assumptions and units.
- A material change invalidates dependent outputs.
- Agent outputs must be traceable to input revisions.
- A verifier must report unresolved conflicts rather than silently selecting a preferred answer.

## 6. Reporting

Each test report includes test ID, objective, fixture revision, expected result, actual result, pass/fail, logs, software version, and reviewer.
