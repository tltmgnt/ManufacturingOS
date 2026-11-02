# Changelog

## 0.3.0 — Offline suite checkpoint

A complete, portable software workflow without real facility or enterprise reads.

- One offline-suite command and responsive review page consolidate all current
  synthetic checks and preserve explicit component/failure/source states.
- Two independently verified pilot runs compare 72 retained files byte for byte.
- Six hand-derived scheduling/cost edge cases retain target misses, seeded
  zero-good output, undefined unit costs and unperformed-work cost exclusions.
- A bounded 54-configuration sweep runs 162 simulations to check conservation,
  accounting, exact replay and horizon-independent full-batch results.
- Complete suite verification checks 274 retained files, both pilot runs,
  16 study bundles, edge/invariant reports, scorecards and the rendered overview.
- Portable deterministic ZIP creation and verification reject unsafe paths,
  aliases, file types, metadata and resource excess before private staging.
- Consolidated CI publishes directory/ZIP artifacts; Chromium retains 16 review
  screenshots while preserving paired-run repeatability.

### Scope and validation

349 automated tests, wheel build, isolated installed CLI workflow, full offline
suite and portable ZIP round-trip verification. CI covers Python 3.11–3.13,
independent core schemas and Chromium. The CI-produced portable ZIP was also
verified after download. Mobile and desktop offline-overview screenshots have
visual review; subsequent automated captures do not imply a new human sign-off.

An intermittent local manifest mismatch occurred in copied-suite test fixtures;
focused and full serial reruns passed. The cause is not established. Verification
continues to reject mismatches, and diagnostics now name differing files; no
integrity checks or tests are bypassed.

All inputs and credentials remain synthetic. The only HTTP source is a loopback
mock. Deterministic output and reconstructed artifacts do not prove measured
accuracy, source authenticity, authenticated approvals or production readiness.
ZIP verification uses a private temporary directory removed afterward and does
not expose a caller-selected extraction target. The runnable examples require a
source checkout; runtime CLI/package dependencies remain unchanged and empty.

The three real-world milestones remain open: authorized facility calibration;
controlled read-only enterprise integration/security acceptance; and an actual
shadow pilot with measured outcomes and qualified acceptance.

The annotated `v0.3.0` tag is created once after successful main-push CI. Existing
tags are preserved. No PyPI publication, deployment or manufacturing authorization
is included.

## 0.2.0 — 2026-11-01

Synthetic rehearsal checkpoint for the advisory prototype. This is a software
release; the three real-world pilot milestones remain open.

- One-command temporary pilot rehearsal with a combined offline review, scorecard,
  explicit failure phases and complete retained fitting/source provenance.
- Four planning cases: reference agreement, deliberate cost discrepancy, missed
  production target and an assumed second-machine capacity remedy.
- Read-only synthetic CSV intake and a loopback mock ERP/MES API, with ephemeral
  read credentials, scope checks and credential-free request/transport records.
- Nine source/access/transport failures rejected before intake/model execution,
  without automatic retry or fabricated fallback results.
- Separate synthetic fitting and held-out evaluation with a frozen candidate,
  overlap/mutation guards and retained baseline/candidate residuals.
- Source-file fingerprints, available Git context and Python/platform metadata;
  source changes during a run prevent a successful scorecard.
- Complete rehearsal verification: exact file inventory, eight reconstructed study
  bundles, loose/bundled report agreement and cross-checked scorecards/provenance.
- Chromium checks at mobile, tablet and desktop widths, screenshot artifacts and
  a reviewed responsive case comparison.

### Scope and remaining gates

All reference data is synthetic. Mock read credentials are not enterprise
identities; the loopback server is not a live ERP/MES connector. Models remain
uncalibrated. The capacity remedy assumes equipment/staffing and excludes purchase,
installation and added fixed costs. Hashes and reconstruction establish supplied
content consistency, not source authenticity, signed approvals or production
acceptance. The runnable examples require a source checkout and are not installed
runtime CLI commands; runtime dependencies remain empty.

Three major milestones remain: authorized real reference data and qualified
calibration; controlled read-only enterprise integration and security acceptance;
and an actual shadow pilot with measured outcomes and qualified acceptance.

### Validation baseline

311 automated tests; complete synthetic rehearsal and eight study bundle
reconstructions; Chromium checks and screenshot generation; independent core
schema checks; wheel build and isolated installed CLI workflow. CI covers Python
3.11–3.13. Selected earlier screenshots have visual review; automated screenshots
for every subsequent revision do not imply a new human visual sign-off.

The annotated `v0.2.0` tag is created once after successful main-push CI. Existing
tags, including `v0.1.0`, are preserved. This does not publish to PyPI, deploy a
service or grant manufacturing authorization.

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
