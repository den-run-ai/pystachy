# Named-escape verification follow-up

Original source: `f3d4d7e33019a589439439ab441c45f77bf753c9` (base `44316e75fabc99108d3188c5b4d0d59e867f4a94`).

Completed original `make verify`: **FAIL**, exit 2; 30/40 stages passed. This is not a clean full-matrix pass when any stage failed.

Recorded interval: 2026-10-18T13:03:20.560769+00:00 to 2026-10-18T14:42:29.596851+00:00; 5949.036 seconds.

| Stage | Result | Seconds | Test counts (passed / failed / expected) |
| --- | --- | ---: | --- |
| `bootstrap` | pass | 177.584 | — |
| `tests-cpython-0` | pass | 292.346 | 1488 / 0 / 1488 |
| `tests-cpython-1` | pass | 276.104 | 1490 / 0 / 1490 |
| `tests-cpython-2` | fail | 233.583 | 1488 / 2 / 1490 |
| `tests-native-0` | pass | 266.114 | 2236 / 0 / 2236 |
| `tests-native-1` | fail | 254.691 | 2230 / 2 / 2232 |
| `tests-opt-off-0` | pass | 271.546 | 2236 / 0 / 2236 |
| `tests-opt-off-1` | fail | 249.157 | 2230 / 2 / 2232 |
| `runtime-cache` | pass | 368.120 | 121 / 0 / 121 |
| `python-free-0` | pass | 301.485 | 1488 / 0 / 1488 |
| `python-free-1` | pass | 200.519 | 1490 / 0 / 1490 |
| `python-free-2` | fail | 167.171 | 1488 / 2 / 1490 |
| `ubsan-0` | pass | 304.424 | 2102 / 0 / 2102 |
| `ubsan-1` | pass | 227.792 | 2106 / 0 / 2106 |
| `ubsan-2` | fail | 220.361 | 2104 / 2 / 2106 |
| `check-ir` | pass | 29.851 | — |
| `runtime-table` | fail | 10.494 | — |
| `gc-self` | fail | 0.007 | — |
| `gc-jit-0` | pass | 260.272 | 1580 / 0 / 1580 |
| `gc-jit-1` | fail | 223.555 | 1576 / 1 / 1577 |
| `gc-aot-0` | pass | 281.775 | 1051 / 0 / 1051 |
| `gc-aot-1` | pass | 280.370 | 1053 / 0 / 1053 |
| `gc-aot-2` | fail | 329.180 | 1052 / 1 / 1053 |
| `benchmarks` | pass | 30.357 | — |
| `rtcheck` | pass | 18.861 | — |
| `re-fuzz` | pass | 24.778 | — |
| `re-probe` | pass | 1.078 | — |
| `rt-abi` | pass | 13.725 | — |
| `inherited-ast` | pass | 0.997 | — |
| `streaming` | pass | 1.075 | — |
| `ffi` | fail | 0.021 | — |
| `list-storage` | pass | 8.385 | — |
| `container-eq` | pass | 6.668 | — |
| `file-buffers` | pass | 6.775 | — |
| `dict-probes` | pass | 7.484 | — |
| `compile-limits` | pass | 33.906 | — |
| `jit-dead-code` | pass | 3.018 | — |
| `unicode-audit` | pass | 47.375 | — |
| `scaling-0` | pass | 229.088 | — |
| `scaling-1` | pass | 287.232 | — |

## Separately attributed checks

The isolated checker correction received `PASS_FOR_ISOLATED_CHECKER_CORRECTION`. Its ten unit checks and separate runtime-table check passed. These are separate receipts and do not repair the original matrix result.

The unchanged baseline GC run reached the 600-second bound (outer exit 124); the candidate also reached the bound. Separate runs and uncontrolled host load leave candidate overhead, cause and stressed IR identity unresolved.

## Limits

- This records the completed original invocation, including failed stages. Later isolated checker success does not replace original results.
- Seven failed corpus shards share one unchanged filesystem-sensitive fixture. GC-stressed self-compilation remains unresolved. The original full invocation failed and the pull request stays a draft.
- Separate baseline/candidate GC runs had uncontrolled host load; no equal-performance, no-regression, causal or stressed-IR-identity claim.
- No new run, CI observation, maintainer acceptance or whole-package compatibility is established by collecting evidence.
- Only relative evidence labels, hashes, counts and timings are published; original logs and absolute workspace paths are excluded.

Machine-readable counts and completed-log hashes are in `named-escapes-2026-10-18-verification.json`. Original dated reports remain unchanged.

## Failure classification

Seven corpus shards failed only `exc_except_attr`: the unchanged fixture expects ENOENT / `FileNotFoundError` when removing `/nonexistent_zz`, whereas this read-only root returns EROFS / `OSError`. The fixture and its recording are unchanged from the base; neither was weakened. The ordinary, native, optimization-off and Python-free corpora each recorded 4,466 passes and 2 failures; UBSan recorded 6,312 passes and 2 failures; GC JIT and AOT each recorded 3,156 passes and 1 failure.

The runtime-table stage found a real candidate integration defect: its expected-input checker recognized only `src/**/*.py`, so it rejected the newly fingerprinted shipped Unicode-name table. The follow-up recognizes exactly that required table, verifies its existence and preserves missing, extra and duplicate input checks.

The GC-self result check took 0.007 seconds after the background compiler had already reached its 600-second bound without producing IR. The unchanged base separately reached the same bound under different, uncontrolled host load. This does not establish equal performance, no regression, a cause or stressed IR identity.

The FFI stage stopped before any assertions because `cc` was unavailable in the isolated PATH. A separate invocation selected the existing Clang explicitly, leaving the harness and compiler unchanged.

## Checks after the original run

The exact reviewed checker correction was integrated after the original command completed. Its ten regression tests passed (0.140 seconds), and the actual runtime consistency checker passed (9.781 seconds): 446 runtime entries, 70 exception classes and 170 functions. The unchanged FFI JIT/AOT harness then passed 125 checks with no failures or reported skips (55.473 seconds). These are separately attributed results, not a rerun or replacement of the failed full matrix. The pull request remains a draft.
