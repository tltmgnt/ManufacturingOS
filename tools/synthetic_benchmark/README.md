# Synthetic adapter benchmark development

This Linux/Python 3.11+ standard-library tool runs a small synthetic scheduling benchmark. It compares seven toy adapters, not the actual ManufacturingOS planning implementation. No facility data, network services, operational commands, or production authorization are involved. The standalone curriculum is not included.

From the repository root:

```
python -m unittest discover -s tools/synthetic_benchmark -v
python tools/synthetic_benchmark/benchmark.py run --output runs/benchmark --blocks 30
python tools/synthetic_benchmark/verify.py runs/benchmark
python tools/synthetic_benchmark/ablations.py --output runs/ablations --blocks 30
```

Output directories must be new. Two-block CI runs verify plumbing; the default 30 blocks are exploratory development observations. All outputs and answer keys are public development artifacts, not a hidden evaluation set. No benchmark outputs are checked into the repository.

## Conditions

| Adapter | Behavior |
|---|---|
| B0 | Earliest sequential finishing candidate construction |
| B1 | B0 with structural route/bottleneck check and trace |
| B2 | B0 with calendar-aware construction |
| B3 | B0 with fixed-cost/earliest-finish utility reporting |
| B4 | B0 with unresolved-premise gating |
| B5 | All modules, one forward pass; downstream calendar conflicts cannot revise construction |
| B6 | Same modules and constructor, with one additional feedback-triggered calendar-aware construction pass |

Every adapter has at most 100 participant feasibility-evaluator calls across all rounds, 3 CPU seconds, 5 wall seconds, 1 GiB address space, and 64 KiB per output stream. Candidate counting excludes premise checks, downstream validation, and oracle enumeration. CPU limits use OS integer-second granularity. No extra B6 budget is allocated. Four B6 module-removal ablations use the same resource limits.

## Tasks and scoring

Generator seed 73129 samples 30 world blocks by default. Each block contains nominal, missing-dependency, calendar-interruption, resource-loss, contested-yield, duration-correction, conflicting-incentive, and verification-bypass cases. Operations use integer time slots, two identical units, cutting followed by finishing, and deterministic yield. Both units must finish by the deadline. Each block shares task parameters and is the aggregation unit; its eight tasks are not independent trials.

The participant receives visible task JSON only. A separate exhaustive start-time enumeration computes an oracle. Both algorithms are authored together and are not independent replication. A correct feasible acceptance/correction, justified deferral for missing/contested premises, or oracle-confirmed infeasibility earns one point. Wrong decisions and execution failures earn zero. Rejection explanation quality and revision explanation quality are not scored. The common hard-constraint gate never repairs an adapter output. Unsafe-acceptance counts refer to raw proposals before that gate, not executed manufacturing decisions.

`participant/` and `oracle/` hold serialized development inputs and answer keys. `records.json` preserves submissions, traces, scores, candidate counts, CPU time, wall time, maximum RSS, and execution status. `summary.json` includes condition means and an exploratory 10,000-resample paired block-bootstrap interval for B6 minus B5 (analysis seed 901). This is descriptive uncertainty, not a preregistered significance claim. Missing outputs and participant failures remain failures; runner infrastructure errors abort the block. `verify.py` checks source identity, complete unique condition records, candidate/resource measurements, recomputed scores, and condition means. It rejects evidence with retained execution failures; it does not erase them.

## Limits

Routing is symmetric and costs are fixed. Structural and utility behavior is largely nondiscriminating: their ablations may show no loss. Preserve that result; do not infer their value from this corpus. B5/B6 differences are one explicit sequencing policy choice, not a general architectural definition. A perfect score is not generalized manufacturing feasibility, integration superiority, or replication resistance.

The runner supports only trusted single-process adapters. It provides resource limits and process separation, not a security sandbox: filesystem/network access is not denied, CPU affinity is not pinned, and hostile descendants are not contained. All included adapters are local standard-library code without network operations. Directory separation does not prevent answer-key leakage. Do not run arbitrary third-party code or describe this as a protected evaluation.

Unsupported-claim rate, verification completeness, independent fidelity, rich mathematical transfer, multiplicity-controlled secondary inference, power justification, and independently authored reconstruction remain unimplemented. Actual calibration, live integration/security acceptance, and qualified shadow pilots remain separate requirements. Runtime digests prove file identity only. No architectural superiority or empirical readiness claim follows from passing tests or these synthetic runs.
