# Development Roadmap

## v0.1.0 baseline and remaining milestones

The release consolidates the reference specifications and advisory prototype into one tested baseline. Phase 1 is implemented with deterministic mock specialists. Phase 2 calculations, simulation, and validation tooling exist, but empirical calibration is not complete. Local evidence capture is an integration foundation, not a live enterprise connector.

Three major milestones remain before a bounded pilot can be accepted:

1. **Authorized reference data and calibrated models.** Select a product family/facility, obtain approved datasets, define acceptance thresholds and held-out checks, and document calibration limits and failures.
2. **Controlled read-only integration.** Implement selected enterprise connectors, identity/access controls, audit/security testing, and the organization's cybersecurity review.
3. **Shadow-pilot evaluation and qualified acceptance.** Establish baselines, measure outcomes without controlling equipment, and obtain engineering, quality, cybersecurity, and management review.

Calibration preparation now has a [protocol](docs/calibration-protocol.md) and [intake worksheet](docs/calibration-intake.md). Authorized facility data and qualified acceptance remain required; this documentation does not complete the milestone.

The original phases below retain their scope. Phase 5 is a separate optional expansion, not part of prototype or pilot acceptance.

## Phase 0 — Reference specification
- Define architecture and agent responsibilities.
- Establish JSON data contracts.
- Document workflow, verification, and safety boundaries.

## Phase 1 — Deterministic orchestration prototype
- Implement input validation and typed domain models.
- Implement orchestrator and agent interfaces.
- Build deterministic mock agents.
- Persist run records and provenance.
- Add unit and integration tests.

## Phase 2 — Manufacturing calculations and simulation
- Add configurable process, capacity, cost, and yield models.
- Calibrate against authorized reference datasets.
- Add scenario simulation and sensitivity analysis.
- Record model assumptions and validation limits.

## Phase 3 — Knowledge and enterprise integration
- Add controlled connectors for approved PLM, ERP, MES, QMS, and supplier sources.
- Begin read-only.
- Add role-based access, audit controls, and security testing.

## Phase 4 — Pilot evaluation
- Select a bounded product family and facility.
- Establish baseline measures before testing.
- Conduct shadow-mode evaluation.
- Obtain engineering, quality, cybersecurity, and management review.
- Report results, failures, and generalization limits.

## Phase 5 — Carefully governed operational expansion
Any write-back or equipment interface requires a separate scope, hazard analysis, cybersecurity authorization, validation, and formal human approval. It is not implied by this roadmap.
