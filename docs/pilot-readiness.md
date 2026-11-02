# Metadata-only pilot handoff preflight

This example checks the three-milestone evidence index while staying offline:

```sh
python -m examples.pilot_readiness examples/pilot-readiness.json
```

The bundled index is deliberately unfilled: three owner references and 15 evidence
records are missing. It reports MISSING_DECLARED_METADATA and exits 1. Unknown
values remain JSON `null`; no facility data, access grant, owner identity or
qualified decision is invented.

Copy the index into the approved working location and record only appropriate
references, revisions and declared raw SHA-256 hashes. Keep sensitive details and
secrets out of this repository. The required evidence groups correspond to the
[handoff worksheets](pilot-milestones.md):

| Gate | Five record groups |
| --- | --- |
| M1 calibration | Data authority, measurement definitions, frozen fit, held-out results, qualified decision |
| M2 integration | Source contract, field mapping, read-only permission, audit/recovery tests, security decision |
| M3 shadow pilot | Entry decisions, frozen plan, baseline, measured results, qualified acceptance |

Each milestone has `milestone_id`, nullable `owner_reference` and an `evidence`
list. Each record has an allowed `requirement_id` and nullable `reference`,
`revision`, `sha256`. Partial or absent records list their missing fields.
Duplicate/unknown IDs, malformed hashes, extra keys and invalid scalar types are
rejected. References are opaque single-line labels of at most 1,024 characters;
they are not resolved as URLs, paths or identities. Input is strict JSON limited
to 128 KiB, including duplicate-key rejection.

A reference/revision/hash triplet is DECLARED_METADATA_PRESENT_NOT_VERIFIED. Even
when all slots and owner references are supplied, the overall result is only
DECLARED_METADATA_COMPLETE_NOT_VERIFIED. Do not use placeholder strings to imply
real records were supplied. The tool cannot distinguish a truthful declaration
from fabricated metadata and performs no source fetch, hash verification,
identity authentication or milestone-closure assessment. Production authorization
always remains false.

Optional output is exclusive:

```sh
python -m examples.pilot_readiness examples/pilot-readiness.json --output runs/pilot-readiness.json
```

The parent directory must exist. Exit 0 means declared metadata is complete,
exit 1 means missing fields, and exit 2 means invalid input or I/O error. Existing
output is preserved. A metadata-complete exit is not model agreement, qualified
acceptance or manufacturing approval. The command is a source-checkout example,
not an installed runtime CLI command.

CI explicitly expects the unfilled template's exit 1 and publishes its report as
`pilot-handoff-metadata-preflight`. It is separate from synthetic model PASS
results and does not change the count of actual remaining real-world milestones.
