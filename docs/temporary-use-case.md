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

Two cases are generated:

- **baseline:** the model agrees with the synthetic reference; the report still
  requires human review and grants no production authorization.
- **cost-disagreement:** a separate deliberately authored synthetic reference
  declares total cost 220 USD. The model remains at 225 USD, retaining a +5 USD
  residual, an observation FAIL and a REVISION_REQUIRED review state. The runner
  exits successfully when this expected failure is correctly detected.

Each case contains its input, preflight, full report, observation checks, offline
HTML review, portable ZIP review and bundle verification. `summary.json` records
both outcomes and explicitly marks empirical calibration incomplete. Open
`baseline/study-review.html` and `cost-disagreement/study-review.html` to compare
agreement with a visible disagreement. Verification checks reconstructability,
not authenticity or approval.

For now, this supports demonstrations, software integration work, failure handling
and review-flow feedback. Real source access controls, connector behavior and
facility performance cannot be validated with this case. When approved data is
available, follow the [calibration protocol](calibration-protocol.md); retain this
synthetic case as a regression example rather than relabeling it as measured data.

## Continuous integration

The Python 3.11–3.13 CI matrix executes both cases. A successful job means the
baseline agrees and the deliberately wrong reference is detected; it does not
mean both observation reports pass. Any unexpected observation status, loss of
the +5 USD residual, loss of the disagreement review requirement, production
authorization, or invalid bundle causes the runner to fail.

Each matrix job uploads `synthetic-bracket-demo-python-VERSION` with the summary,
case inputs, reports, HTML reviews, ZIP bundles and verification records. Download
it from the GitHub Actions run and open the case HTML files locally. Artifacts
contain synthetic data only and follow the repository's default retention period.
