# Native I/O qualification record for alpha.3

The versioned alpha.3 candidate is merged at [04860a83618e744c6f461761b6ee7fdbbe21f985](https://github.com/den-run-ai/pystachy/commit/04860a83618e744c6f461761b6ee7fdbbe21f985), tree `bc34d9b1a3f648fbae6368e1c78485baf8d60c99`. All four required release workflows passed on this exact commit: 77 successful jobs and two expected PR-only skips. Performance smoke also passed. This record preserves the earlier fixture failures, bounded fixes, qualified PR trees and complete merged-main evidence for [#1216](https://github.com/den-run-ai/pystachy/pull/1216) and [#1217](https://github.com/den-run-ai/pystachy/pull/1217). Public alpha.3 publication remains pending.

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

## Third observed fixture failure and bounded TCP correction

The [e4e81296 records](e4e81296) preserve a successful Linux distribution run (5m21s; netio step 81s; 50 harness tests; all six modes and 300-cycle ASan/UBSan ownership with leak detection), and the third macOS oracle failure. Lint passed in 14m43s. After native bootstrap/installation smoke, the oracle's accepted TCP descriptor raised BlockingIOError during its payload read. Bridge/native netio and drain modes were not reached. The release-preparation run at `5360270d` reproduced the same failure.

Both original ZIPs and byte-identical reports are included. All 170 reported Linux source files and all six macOS report source hashes match `e4e81296`; checkout `80640beed9493821ec4895050eff2e94e5e935a9` has its identical tree.

[b52facdc](https://github.com/den-run-ai/pystachy/commit/b52facdc86115e818325c54b82ac6f4d846d83ff) explicitly sets the accepted kernel descriptor to blocking mode. Independent real-socket controls also reproduced all four legal short-transfer failures. Tiny TCP exchanges now accumulate exact bytes with positive bounded progress, size checks, early-EOF rejection and unchanged outer timeouts. The nonblocking connection and EOF readiness phases remain. Runtime implementation and APIs are unchanged.

[Local validation](accepted-transfer-fix-local/validation.json) records 53 passing harness tests, twelve oracle/bridge scenarios repeated twice, Ruff and verified hosted IR emission. Controls check real kernel flags, one-byte transfers, zero/invalid progress, early EOF and corrupted data. The local commit `6cc496ab` and published `b52facdc` share tree `e21114a45febccb4aaca65008cda948cf3325112`. The completed qualification below subsequently validated that corrected tree on native macOS.


## Completed qualification of the corrected tree

The [b52facdc records](b52facdc) preserve both original artifact ZIPs, all seven unmodified reports, native step logs, compiler identity, final job/run/artifact metadata and a SHA-256 manifest.

| Exact head and platform | Completed evidence |
|---|---|
| `b52facdc`, Linux x86-64 | Distribution 4m21s; netio 67s; 53 harness tests; twelve socket cases repeated twice through hosted and native compilers; socket and drain parity in all six modes; 300 ASan/UBSan ownership cycles with leak detection enabled. |
| `b52facdc`, macOS ARM64 | Distribution 9m08s; netio 45s; twelve socket cases and the completion-order drain scenario in all six modes using the actual native compiler, on macOS 15.8.2 / Python 3.13.16. |
| `c355f306`, macOS ARM64 | Distribution 9m25s; netio 45s; the same twelve socket cases and drain scenario passed all six modes on the versioned candidate. Original ZIP, reports, source checks and native log are in [c355f306-macos](c355f306-macos). |

The six modes are CPython oracle, CPython bridge, JIT, AOT, JIT GC stress and AOT GC stress. Stress reports explicitly record the applicable flag as 1. The Linux ownership run used `ASAN_OPTIONS=detect_leaks=1`. All downloaded archive digests match GitHub metadata. Every recorded source hash matches its immutable source commit: 170 unique paths for b52 Linux, nine for b52 macOS and nine for c355 macOS.

Both [b52 CI](https://github.com/den-run-ai/pystachy/actions/runs/42860006680) and [c355 CI](https://github.com/den-run-ai/pystachy/actions/runs/42860011761) passed all sixteen jobs on attempt 1, without missing, skipped, cancelled or failed CI groups. Lint, Performance smoke and Submission format also passed; the same-repository fork-only DCO job is an expected skip. All jobs remained within the existing fifteen-minute limit.

The independently verified [aggregate records](pr-gates) contain 41/41 passing checks and the exact twelve report groups. The reports' 58 compiler/runtime hashes match their checkouts. Native JIT and AOT each cover all 4,295 cases exactly once, with 4,541 checks per mode; the 81-case alternative-configuration selections match the trusted sampler. Counts from the separate execution-mode groups and the shared-rejection suite use different conventions and must not be conflated.

[b52 Lint](https://github.com/den-run-ai/pystachy/actions/runs/42859999115) actually ran the nine-job Lean build, all three theorem axiom audits and all 28 boundary tests. [Stacked c355 Lint](https://github.com/den-run-ai/pystachy/actions/runs/42860010890) legitimately skipped Lean because its additional diff was only VERSION and two documentation files. The complete b52 Lean evidence remains material to this candidate; a skipped step is not reported as execution.

The original b52 checkout `02ea4fcb7b52a5c7cac2d2332f24902b2541ec7e` has tree `e21114a45febccb4aaca65008cda948cf3325112`. The original c355 checkout `2b454363fa787023952ed6867a9722c18d6e0840` and its retargeted-main checkout `3a3804599ff0add3779791df6a0391c44c8edd28` both have the exact tested tree `bc34d9b1a3f648fbae6368e1c78485baf8d60c99`. Retargeting changed the comparison base, not the tested file tree.

These are completed PR-profile gates. A public alpha.3 release is not established by this checkpoint.


## Exact merged-main qualification

The [gate summary](main-04860a83/gate-summary.json) identifies the actual merged commit, tree, version, all workflow runs, preserved feature heads and remaining release scope. All seven original feature heads are ancestors of `04860a83`; the merged tree is identical to the reviewed and tested candidate.

| Exact-main workflow | Result |
|---|---|
| [CI 42864866935](https://github.com/den-run-ai/pystachy/actions/runs/42864866935) | 68 successful jobs; two expected PR-only placeholder skips; all 70 entries inspected. |
| [Installation 42864866843](https://github.com/den-run-ai/pystachy/actions/runs/42864866843) | All seven jobs passed. |
| [Lint 42864866830](https://github.com/den-run-ai/pystachy/actions/runs/42864866830) | Passed, including actual Lean execution. |
| [Packages 42864866834](https://github.com/den-run-ai/pystachy/actions/runs/42864866834) | Passed. |
| [Performance smoke 42864866829](https://github.com/den-run-ai/pystachy/actions/runs/42864866829) | Passed; all 49 comparisons across eleven workloads were classified ok. |

All five runs completed successfully on attempt 1. The four required release workflows total **77 successful jobs and two expected skips**. The longest job took 13m15s, below the unchanged fifteen-minute cap; Lint took 11m44s. No source-test cancellation, retry, timeout extension or coverage waiver was used.

### Full CI and Lean evidence

The [CI/Lint bundle](main-04860a83/ci-lint) retains both original aggregate ZIPs, exact artifact/commit metadata, raw workflow/job metadata and complete aggregate/Lint logs as gzip, the readable Lean step log and a checksum manifest. Its [independent audit](main-04860a83/ci-lint/audit-summary.json) validates both reports as full/all on the clean exact-main checkout: **56/56 checks across all 33 groups per architecture**, with all 58 compiler/runtime hashes and the complete source fingerprint matching.

On each architecture, native, optimization-disabled and Python-free suites report 6,946 checks each; UBSan reports 9,082; GC JIT and AOT report 4,541 each. GC compiler IR identity covers all 4,295 cases plus 254 syntax cases. Both opt-in sweeps cover all 2,275 programs in two modes, preserving the existing exception manifests.

Full-profile native reports attest deterministic shard/check counts, which were independently reconstructed from the trusted checkout. Exact case/mode identities were checked where recorded, including both opt-in sweeps. The audit distinguishes these evidence forms explicitly.

The actual Lint log verifies the pinned Lean archive checksum, nine successful Lean build jobs, all three theorem axiom audits and all 28 boundary tests, with `LEAN_BOUNDARY_REQUIRED=1` and zero skips. This execution is tied to merged main, independent of the earlier stacked-PR skip.

### Installation and native I/O evidence

The [Installation bundle](main-04860a83/installation) preserves all twelve raw netio reports, three original artifact ZIPs, native compiler identities, installer/netio logs, pinned-source proofs and final run/job metadata. Its [qualification summary](main-04860a83/installation/qualification-metadata.json) confirms all seven jobs passed, including four platform installs and three exact-commit pip/uv source installs.

Linux x86-64 and ARM64 each passed all twelve socket cases repeated twice and all drain modes through hosted and native compilers. macOS ARM64 passed the twelve cases and drain scenario through its actual native compiler. All six oracle/bridge/JIT/AOT/GC modes ran on each qualified netio platform. Each Linux architecture passed 53 harness tests and 300 ASan/UBSan ownership cycles with leak detection enabled. Source verification covers 170 unique paths on each Linux architecture and nine on macOS ARM64.

The four platform installers report `v0.4.0-alpha.3` at `04860a83`. macOS Intel retains the existing installer/JIT/AOT/GC/cache checks; dedicated native netio coverage applies to the three platforms stated above. Prior PR evidence was not substituted for these exact-main results.

### Additional gates and remaining scope

The [workflow-gates bundle](main-04860a83/workflow-gates) preserves package and performance records. The bounded paired performance report compares `ad3d0c0e` with `04860a83`, with matching runner/workload source hashes and no warning or unconfirmed comparison.

Variants was **not triggered and not executed on 04860**: none of its six watched paths changed. Its [policy record](main-04860a83/workflow-gates/variants-policy.json) verifies the 39-path diff and release policy. The 24-job ad3 Variants result is retained as historical evidence for unchanged source, not described as a current-head run.

The original PR checks include older metadata-only runs cancelled during edits/ready transitions under the existing concurrency policy. Their newer same-head Submission format checks passed before merge. Both fresh Codex reviews completed with no findings, and all review threads were clear.

The alpha.3 milestone remains open with ten completed items and five excluded drafts: libuv #1146/#1155/#1158 and numerical workers #1088/#1136. The broader Any containment work in #1210 and documented #1182/#1207 compatibility limits remain open. The native bridge remains an optional source example outside binary packages, and Lean retains its normalized-model and trusted-bridge limits. Public native archives, Docker images and PyPI publication for alpha.3 are separate remaining release work.
