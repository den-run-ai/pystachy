# Native I/O qualification record for alpha.3

This checkpoint preserves the observed failures, successful Linux runs and bounded fixture fixes for [PR #1216](https://github.com/den-run-ai/pystachy/pull/1216). At this checkpoint, fresh qualification of `e4e81296c7f322e04451980c882fa254d1eb0b62` is running in [CI 42855237339](https://github.com/den-run-ai/pystachy/actions/runs/42855237339). It is not a completed macOS or release gate.

This research branch is evidence only and must not be merged into main.

## Observed runs

| Exact head | Linux evidence | macOS result |
|---|---|---|
| `37a9db95268b767e75f05091c5a8946a42300c77` | Distribution passed in 5m40s; netio step 85s; 48 harness tests, six hosted/native modes and 300-cycle ASan/UBSan ownership with leak detection passed. Lint passed in 12m00s. | The CPython oracle failed on an exact enabled socket-option value assertion, before bridge/native execution. |
| `cbb02637a069250680d9c950edb5315ed62a8d88` | Distribution passed in 5m20s; netio step 80s; 49 harness tests, all six modes and ownership with leak detection passed. Lint passed in 14m23s. | The corrected option case passed. The CPython oracle then failed the refused-connect fixture, before bridge/native execution. |

The directories [initial-37a9](initial-37a9) and [cbb02637](cbb02637) preserve original artifact ZIPs, byte-identical extracted reports, compact step logs and verification metadata. All archive digests were checked against GitHub's artifact digests. Each Linux record covers 170 distinct committed source files; each failed macOS report records six source hashes. Every reported source hash was compared with the exact Git object. The actual PR checkout `3512f3d4d69da489f922c680463597dec5574a9d` has the same full tree as `cbb02637`.

Reports from failed or incomplete runs remain failures. Source verification and a successful Linux run do not establish macOS execution.

## Bounded fixes

[8718dfe1](https://github.com/den-run-ai/pystachy/commit/8718dfe1d11f9c818588569705167cb6b614f887) checks boolean socket options as disabled zero/enabled nonzero. Its real-socket regression reproduces the old assertion failure with enabled value 4 and rejects wrong states. The raw integer was not recorded in the failed macOS artifact; 4 is explained by Darwin's implementation, not claimed as an observed CI value. Local checks: 49 harness tests, twelve oracle/bridge scenarios repeated twice, Ruff and verified hosted IR. See [option-fix-local](option-fix-local).

[e4e81296](https://github.com/den-run-ai/pystachy/commit/e4e81296c7f322e04451980c882fa254d1eb0b62) reserves distinct client/destination ports, releases the destination, then connects. The prior readiness deadline and exact refusal error checks remain. Its regression reproduces the old fixture error and rejects immediate success, missing readiness and a zero completion error. Local checks: 50 harness tests, twelve oracle/bridge scenarios repeated twice, Ruff and verified hosted IR. See [refused-fix-local](refused-fix-local). External port reuse can cause a test failure; it cannot turn unexpected success into a pass.

Both fixes were independently reviewed against the published code and Apple's TCP/socket behavior. Runtime implementation and APIs are unchanged. Generated IR is reproducible from the recorded commands and immutable source; emission metadata is retained here.

## Scope and verification helper

The optional bridge remains a source-checkout example. These records do not establish a general networking performance improvement, unrestricted asynchronous Python, or new packaged standard-library support.

[verify_netio_artifact.py](verify_netio_artifact.py) preserves downloaded bytes, checks archive/source hashes and records missing or failing reports. CI logs and report mode lists supply execution evidence; the helper's hash checks alone are not execution proof.

The separate [Any-boundary audit](https://github.com/den-run-ai/pystachy/blob/a2a083f3e55de040de98eb52e6f94683a3e54e0a/research/alpha3-boundary-audit-20261110/README.md) and [merged-main verification](https://github.com/den-run-ai/pystachy/pull/1215#issuecomment-6772758630) cover the compiler integration.
