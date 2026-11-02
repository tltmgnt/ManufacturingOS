# Portable offline suite ZIP

Package a successful offline suite for copying or review:

```sh
python -m examples.offline_suite --output runs/offline-suite
python -m examples.offline_suite_bundle create runs/offline-suite --output runs/offline-suite.zip
python -m examples.offline_suite_bundle verify runs/offline-suite.zip
```

The ZIP destination must be outside the suite directory, with an existing parent.
Existing destinations are preserved. Creation verifies the original directory and
the completed ZIP before writing a new output file. Failed I/O while writing may
leave a partial new file; choose a new destination for reruns.

The writer uses fixed timestamps, sorted paths and regular-file metadata. Repeating
creation from unchanged content in the same environment yields identical bytes;
cross-environment compression equality is not guaranteed.

## Verification and staging

ZIP metadata is checked before any staging directory is created: canonical relative
paths, duplicate/case/Unicode aliases, file/directory collisions, portable device
names, regular-file types, sizes, entry count, compression and directory structure.
Encryption, multipart/ZIP64, comments/extra metadata and unsupported compression
are rejected. The format uses deflated files only, with implicit directories.

Payloads are CRC-checked and bounded, then written exclusively into a private
system temporary directory. Archive permissions are not applied. The complete
suite verifier runs there, reconstructing both pilot runs, 16 study bundles,
six edge cases and 54 invariant configurations. The temporary directory is removed
on success or failure; no caller-selected extraction directory is exposed.

Limits: 256 MiB archive, 256 MiB total decoded content, 32 MiB per file, 500 files,
and a 1 MiB central directory. The existing suite/manifest limits also apply.
Exit 0 means content verification passed; exit 2 means invalid content or I/O error.
No real system, facility data, external network or real credentials are used.

CI uploads the portable ZIP as `offline-synthetic-suite-bundle`, alongside the
existing directory artifact. GitHub's artifact download may wrap it in another ZIP;
verify the inner `offline-suite.zip` with this command.

Hashes, CRCs and reconstruction check supplied content consistency, not source
authenticity, identity, measured accuracy, approval or production authorization.
Use the recorded matching source checkout/environment. This repository example
adds no third-party runtime dependency and is not an installed runtime CLI command.
