# Temporary synthetic use case: small bracket batch

This temporary case lets development and workflow review continue without a
facility export. It does not complete empirical calibration or pilot acceptance.
All source observations are synthetic and explicitly retain that label.

Run from the repository root with Python 3.11 or later:

```sh
python -m examples.temporary_use_case --output runs/temporary-bracket-demo
```

Choose a fresh output directory each time. No network service or enterprise
credentials are used. The runner writes under the selected directory and refuses
an existing path. If execution fails, partial files can remain for diagnosis;
choose another new directory for a rerun. The module is a repository example,
not an installed CLI command.

The scenario starts three brackets through cutting (1 hour per piece) and
finishing (2 hours per piece), each on one machine. There is no setup or scrap.
The horizon is 5 hours and the demand is two good brackets. The synthetic rates
are material 5 USD/start, cutting 30 USD/hour and finishing 20 USD/hour.
The source study also exercises seeded replications and input uncertainty;
those outputs are model demonstrations rather than empirical estimates.

| Outcome | Hand reference |
| --- | --- |
| Good brackets by 5 hours | 2 |
| WIP at 5 hours | 1 |
| Eventual good brackets | 3 |
| Batch completion | 7 hours |
| Full-batch cost | 225 USD |
| Cost per eventual good bracket | 75 USD |

The full cost is 15 USD material + 90 USD cutting + 120 USD finishing.
It includes processing after the 5-hour horizon.

Four cases are generated:

- **baseline:** the model agrees with the synthetic reference; the report still
  requires human review and grants no production authorization.
- **cost-disagreement:** a separate deliberately authored synthetic reference
  declares total cost 220 USD. The model remains at 225 USD, retaining a +5 USD
  residual, an observation FAIL and a REVISION_REQUIRED review state. The runner
  exits successfully when this expected failure is correctly detected.

- **target-miss:** demand increases from two to three brackets by hour 5. The
  same physical process still produces only two in that horizon. All six reference
  checks PASS, but `target_met` is false and the report retains
  SIMULATED_TARGET_MISS with REVISION_REQUIRED. Eventual completion at hour 7
  does not satisfy the earlier deadline.

- **capacity-remedy:** keep the three-bracket target and add a second identical
  finishing machine. Cutting completes at hours 1, 2 and 3; two finishing machines
  complete the brackets at hours 3, 4 and 5. The reference checks PASS and the
  model meets the target, but human review remains required. Processing costs
  remain 225 USD because total busy hours are unchanged. This excludes equipment
  purchase, installation and added fixed costs; staffing and actual machine
  availability are unverified. It is a synthetic alternative, not a purchase
  recommendation or production approval.

Open `runs/temporary-bracket-demo/index.html` for an offline comparison of all
four cases, target counts, cost residuals and review states. The page links to
each case review, JSON report and ZIP bundle. Keep the directory tree together
when copying or downloading the results. Narrow screens show labeled case cards
so target outcomes, review states and file links remain in view without horizontal
scrolling.

Each case contains its input, preflight, full report, observation checks, offline
HTML review, portable ZIP review and bundle verification. `summary.json` records
all four outcomes and explicitly marks empirical calibration incomplete. Open
`baseline/study-review.html` and `cost-disagreement/study-review.html` to compare
agreement with a visible disagreement. Verification checks reconstructability,
not authenticity or approval.

For now, this supports demonstrations, software integration work, failure handling
and review-flow feedback. Real source access controls, connector behavior and
facility performance cannot be validated with this case. When approved data is
available, follow the [calibration protocol](calibration-protocol.md); retain this
synthetic case as a regression example rather than relabeling it as measured data.

## Continuous integration

The Python 3.11–3.13 CI matrix executes all four cases. A successful job means the
baseline agrees and the deliberately wrong reference is detected; it does not
mean every observation report passes or every production target is met. The
target-miss case must retain its shortfall finding despite reference agreement. Any unexpected observation status, loss of
the +5 USD residual, loss of the disagreement review requirement, production
authorization, or invalid bundle causes the runner to fail.

Each matrix job uploads `synthetic-pilot-rehearsal-python-VERSION` with the summary,
case inputs, reports, HTML reviews, ZIP bundles and verification records. Download
it from the GitHub Actions run and open the case HTML files locally. Artifacts
contain synthetic data only and follow the repository's default retention period.

## Browser checks and screenshots

The separate `demo-browser` CI job installs development-only Playwright and
Chromium. It loads the offline comparison at widths 375, 768 and 1440, checks
case outcomes and viewport overflow, checks local links, and follows each case's
review link in Chromium. External HTTP/HTTPS requests are blocked.

The `synthetic-demo-browser-review` artifact includes sixteen screenshots (three
offline-suite widths, three combined-review widths, three failure-review widths,
three planning-comparison widths and four full case reviews) plus the generated demo files.
Automated browser checks do not replace human visual review of those screenshots.
Failures retain available files for diagnosis.

To reproduce from the repository root:

```sh
python -m pip install -r requirements-browser-tests.txt
python -m playwright install chromium
python -m examples.offline_suite --output runs/browser-offline-suite
python tests/check_demo_browser.py
```

Use fresh output directories. The browser dependencies are not installed with
the ManufacturingOS runtime package.

The consolidated artifact stores this component under `planning/`. Open the top-level `index.html` to review the entire rehearsal.
