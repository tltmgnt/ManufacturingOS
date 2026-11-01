# Read-only synthetic export intake rehearsal

This repository example rehearses a source-export → derived reference → study →
review-bundle handoff using a bundled synthetic CSV. It is not an ERP/MES
connector, authenticated source, or completion of the integration/calibration
milestones. It deliberately accepts only the `synthetic` data-kind label.

From the repository root:

```sh
python -m examples.synthetic_export_intake --output runs/export-intake
```

The command reads the bundled `examples/synthetic-batch-export.csv` without
modifying it, makes no network requests, and writes only to a new output directory.
There is no live-source or arbitrary export selector. Existing outputs are
preserved. Failures during writing may leave partial output; use a fresh directory
for a rerun. The example is not an installed runtime CLI command.

## Source contract and transformations

The CSV header defines the exact supported columns and order. It contains one
completed batch: explicit product/design and facility/revision IDs, batch starts,
horizon counts, final counts, completion time in hours, and total full-batch cost
in USD. `batch_id` identifies the observational unit; replication runs do not
increase the observation count. Multi-batch aggregation is outside this example.

The importer rejects missing/extra/duplicate columns, extra rows, incomplete
values, inconsistent counts, noninteger counts, nonfinite/negative numbers,
context mismatch and time/WIP contradictions. The raw parser is bounded to
64 KiB. Units are fixed by the header, not inferred. Unit cost is total cost divided
by eventual good output; zero-good batches are unsupported by this particular
unit-cost rehearsal and rejected explicitly. They must not be silently excluded
from a real calibration dataset.

Each horizon count must reconcile with starts, final good/scrap must reconcile
with starts, and horizon dispositions cannot exceed final dispositions. These
checks establish internal consistency, not measurement truth. A single batch is
not a statistically representative population. This deterministic synthetic case
uses the same batch and horizon definitions as the model.

## Outputs and traceability

- `source-export.csv`: original CSV bytes, also captured as separate evidence.
- `derived-reference.json`: selected numeric observations derived from the CSV,
  captured separately and bound to the exact study context.
- `intake-provenance.json`: raw/derived hashes, batch ID, transformation version,
  observation count and explicit synthetic/calibration limits.
- Study input, preflight, full report, offline HTML, verified ZIP bundle, and bundle
  verification record. The bundle retains both raw CSV and derived reference in
  its embedded input snapshot.

The baseline export gives two good brackets by hour five, one WIP, three eventual
good brackets, seven-hour completion and 225 USD full-batch cost (75 USD/good
bracket). Tests change the source cost to 220 USD and require a visible +5 USD
residual and revision-required result, proving the comparison uses export values.

The Python 3.11–3.13 CI matrix runs the rehearsal and uploads
`synthetic-pilot-rehearsal-python-VERSION`. Runtime dependencies are unchanged.
Hashes prove supplied-byte consistency, not origin or organizational authorization.

When authorized real exports become available, use the [calibration intake](calibration-intake.md)
to agree on source permissions, actual measurement definitions, accounting scope,
missing outcomes, multiple batches, held-out evaluation and acceptance criteria.
Real data needs its own reviewed adapter and access controls; do not relabel this
fixture or weaken its synthetic-only guard to declare a live integration complete.

The consolidated artifact stores this component under `intake/`. Open the top-level `index.html` to review the entire rehearsal.
