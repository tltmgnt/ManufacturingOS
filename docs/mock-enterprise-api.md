# Read-only mock ERP/MES API rehearsal

This is a local integration rehearsal using the same synthetic batch export as
the file-intake example. It does not connect to an enterprise system or complete
identity, access-control, cybersecurity or actual integration acceptance.

From the repository root:

```sh
python -m examples.mock_enterprise_api --output runs/mock-api
```

The combined `examples.temporary_pilot` command also includes this component under
`api/`. Open its `study-review.html`; inspect `transport-provenance.json`,
`mock-request-audit.json` and `api-rehearsal-summary.json` alongside the retained
source export and verified study bundle.

## Transport contract

- The server binds only `127.0.0.1` using an automatically selected port. It starts
  for the rehearsal and shuts down afterward. No external host, credentials,
  configuration URL or proxy is used.
- The client sends exactly one GET to `/v1/batches/demo-batch-001/export`. The
  fixture returns CSV bytes with a fixed source revision, explicit content length
  and SHA-256 ETag. POST, PUT, PATCH and DELETE return 405; unknown paths return 404.
- The client has a three-second socket timeout and a 64 KiB response limit. It
  rejects non-200 responses (including redirects and throttling), unexpected
  content type/revision, transfer encoding, invalid content length, hash mismatch
  and invalid/non-synthetic export records. There is no automatic retry.
- Received bytes feed the existing intake pipeline, which preserves raw and
  derived evidence and reconstructable study bundles. The retained source hash
  must match the transport hash. The original fixture is unchanged.

The command reads only bundled fixtures and creates a new output directory.
Existing paths are rejected before server startup. Failed runs exit 2 and may
leave partial outputs after writing starts; use a fresh directory for a rerun.
These are repository examples, not installed runtime CLI commands.

## Meaning of the checks

The local audit records request method, path and status; it is not a durable,
authenticated enterprise audit log. Revision and hash agreement establish supplied
byte consistency, not source authenticity. Loopback HTTP intentionally has no TLS,
credentials, identities, permission model, secret storage or token renewal.

The mock source has no write behavior. Method-rejection tests demonstrate this
fixture's contract; they do not prove real ERP/MES permissions. The client does
not accept arbitrary URLs or forward authorization headers. HTTP errors fail
explicitly for review rather than concealing them with fabricated data.

CI runs the mock transport as part of the combined rehearsal across Python
3.11–3.13 and retains its evidence in the consolidated artifact. Before any real
connector, select the system and supported API, authorize a dataset and read-only
service identity, define scope/refresh/retry limits, and complete source, access,
audit and security review. Production authorization and live integration completion
remain false throughout this rehearsal.
