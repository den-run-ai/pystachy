# c355 macOS native I/O evidence

The completed macOS ARM64 distribution job passed on the exact release-preparation candidate. This record preserves the original CI evidence; it is not publication or a final versioned-main release gate.

- PR: https://github.com/den-run-ai/pystachy/pull/1217
- Published head: `c355f3064ec48077abe2b2b17f81019fad49195d`
- Published tree: `bc34d9b1a3f648fbae6368e1c78485baf8d60c99`
- Local clean comparison commit: `206a2c70a7c1ca52d7ec1836996ff0851b2de92f`, same tree.
- CI run: https://github.com/den-run-ai/pystachy/actions/runs/42860011761
- Job: https://github.com/den-run-ai/pystachy/actions/runs/42860011761/job/129989571236
- Artifact: https://github.com/den-run-ai/pystachy/actions/runs/42860011761/artifacts/13784879644
- Artifact ZIP SHA256: `d7ea89064f3289abe43d36c199ec3d9a66dd3f76a7b4d441b401d9fd4d7b3f5b`

## Observed results

Both JSON reports declare pass on macOS 15.8.2 ARM64 and Python 3.13.16. The socket/selector report records all 12 cases in all six modes: CPython stdlib oracle, CPython bridge, native JIT, native AOT, JIT with program GC stress, and AOT with GC stress. The drain report records successful completion-order and binary-output parity in all six modes.

The entire Mac distribution job passed in 9 minutes 25 seconds. Its native kqueue/pipe step passed in 45 seconds. The full job also passed bootstrap, installer and hosted/native JIT/AOT smoke, and clean pip/uv installation checks. Linux-only steps and Mac source/archive smoke are intentionally skipped by the workflow.

## Exact-source verification

The ZIP bytes match GitHub's artifact SHA256. The two JSON files are preserved byte for byte from that ZIP. All six source hashes shared by both reports and all three additional drain/checker/probe hashes match files in the clean local candidate tree; the published commit metadata independently records that same tree. The source-verification JSON records every expected and observed hash and asserts both native GC settings.

The report identifies nine example/checker source files; it does not provide a separate compiler-binary digest. The completed job log records checkout, bootstrap, commands and CI source identifiers. This comparison verifies retained evidence and does not rerun or broaden the runtime checks.

## Files

- `netio-c355-macos.zip`: original GitHub artifact archive.
- `netio-macos.json`, `netio-drain-macos.json`: unmodified extracted reports.
- `artifact-metadata.json`, `job-metadata.json`, `workflow-run-metadata.json`, `published-commit-metadata.json`: API provenance at capture.
- `source-verification.json`: exact-source comparison, report assertions and completed CI result.
- `retarget-merge-metadata.json`: unchanged tested tree after retargeting to main.
- `macos-distribution-job.log`: complete job log as returned by GitHub.
- `native-kqueue-pipe-step.log`: unmodified relevant command/environment/output block.
- `SHA256SUMS`: checksums for the preserved files.

The CI workflow completed successfully on the exact c355 head. The metadata now records that completed result. After retargeting to main, GitHub's synthetic merge 3a3804599ff0add3779791df6a0391c44c8edd28 has parents ad3d0c0eda3ccf2ae2a35d38c92f345205e853ab and c355f3064ec48077abe2b2b17f81019fad49195d, with exactly the tested bc34d9b1a3f648fbae6368e1c78485baf8d60c99 tree. The compact retarget-merge metadata preserves that independently fetched identity. This is still PR candidate evidence; final versioned-main release workflows remain a separate gate.
