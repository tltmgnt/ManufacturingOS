# Changelog

## 0.1.0 — 2026-11-01

Initial alpha release of the advisory ManufacturingOS prototype.

- Deterministic mock-agent planning, typed contracts, revision fingerprints, and audit records.
- Serial-route capacity/cost/yield estimates, finite-batch scheduling, downtime calendars, full-batch costs, uncertainty sampling, and seeded replication/replay.
- Evidence metadata policies, selected-file capture, captured-content hashes, and context-bound reference checks.
- Integrated studies and preflight validation, comparisons, reviewer annotations, scenario campaigns, offline HTML reviews, and verified portable bundles.
- An installable, dependency-free runtime CLI and packaged core JSON Schemas.
- Strict bounded JSON ingestion and CI/distribution checks on Python 3.11–3.13.

### Release scope

The specialist agents remain mocks. Supplied examples and reference cases are synthetic. Models are uncalibrated, source identities/reviewer roles are declarations, and verification is not a signature or manufacturing approval. No enterprise connector, authenticated approval service, write-back, equipment control, or production release is included. Secure selected-file capture requires supported POSIX operations. Browser visual QA is still outstanding; HTML structure, escaping, and links have automated coverage.

### Validation baseline

252 automated tests; isolated wheel installation and complete CLI workflow; independent checks of two Draft 2020-12 schemas (four positive fixtures, 25 invalid fixtures, three semantic-boundary cases). CI runs the same release checks on Python 3.11, 3.12, and 3.13. Passing software checks does not establish facility calibration or production readiness.

The annotated `v0.1.0` tag is created once by GitHub Actions only after the tested main-branch push succeeds. Existing tags are never moved. This workflow does not publish to PyPI, deploy a service, or authorize manufacturing.
