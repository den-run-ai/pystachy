# Alpha.2 bounded build cost and memory comparison

Exact source homes: alpha.1 `a73c56c92f3aad4b490307a5d1b882e487a57f55`; alpha.2 `80490143498d149d407343ba1cb7aedb1db2d2c5`. The retained final fixed-point binaries are bound to these homes by the verified identity manifest; only three Lean checker/test files changed since their builds.

Three alternating pairs per workload used one CPU, private warmed runtime caches, program caching disabled and one build at a time. All 24 warmup/measured executables matched pinned CPython output. Runtime cache bytes and clean source/binary identities stayed unchanged.

| Workload | Build seconds, alpha.1 → alpha.2 | Change | Peak RSS KiB, alpha.1 → alpha.2 | Change | Executable bytes, alpha.1 → alpha.2 | Change |
|---|---:|---:|---:|---:|---:|---:|
| numeric | 1.450922 → 0.396689 | -72.7% | 93,540 → 88,136 | -5.8% | 107,072 → 145,200 | +35.6% |
| json | 12.863427 → 9.186604 | -28.6% | 140,776 → 133,436 | -5.2% | 668,808 → 701,704 | +4.9% |
| copy_float | 1.377891 → 0.227626 | -83.5% | 93,604 → 85,492 | -8.7% | 112,304 → 151,048 | +34.5% |

These are medians of three observations in this local Linux x86-64 environment with LLVM 18.1.3 and CPython 3.13.16. They show a bounded warm-build tradeoff, not a broad runtime-speed or application-memory claim.

Memory was collected by a fresh pinned-Python `os.wait4` wrapper for each command. Linux `ru_maxrss` is reported in KiB, with waited-descendant resource accounting; it is not the sum of simultaneously resident child processes. Stdout/stderr went to ordinary files, and no process sampling was used. The six cold/setup warmup records are retained separately and excluded from the medians.

No steady-state runtime or startup comparison is derived from the untimed correctness executions. The fresh remote Performance smoke artifact supplies its separate JIT/AOT timing observations.

Full raw observations, both source/binary manifests, all commands, logs, toolchain hashes, CPU affinity and relevant environment settings are retained beside this report.
