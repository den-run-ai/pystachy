# Graph-copy regression: current replay and memo profile

Research evidence only; do not merge this branch. Maintained guard: PR #869. Runtime candidate: PR #872. Tracked remaining costs: #780.

Frozen input is the original `tools/dynany_bench.py graph 4000`, SHA256 `2546632715f4df66b2953200f1a41c9d52671e4eee416c9d53a9307acc6dd388`; checksum 670230 in CPython/JIT/AOT.

Revisions: parent `f4b9396167e41616707938ca34d99f359a706622`; #821 `185849790523815d0f63ab1a8b33c17549bf31b4`; current main `46fd53536afac60760b15f068641f7f238f964fe`. CPython 3.13.16 and LLVM 18.1.3, CPU 0, private runtime homes/caches, sanitized settings, interleaved processes and shared-host work preflight. Exact source, compiler and toolchain hashes, all samples and load averages are in the raw JSON.

## Current replay

| JIT processing CPU median | Parent | #821 | Main | Main/parent | Main/#821 |
|---|---:|---:|---:|---:|---:|
| Initial five processes |45.942 ms|64.306 ms|66.668 ms|+45.12%|+3.67%|
| Confirmation five |58.148 ms|84.972 ms|80.316 ms|+38.12%|-5.48%|

These are fresh shared-host samples, not pooled with the previous historical campaign. Load drift is visible; retain every outlier. The regression persists directionally on current main, while main-versus-#821 differences are inconclusive. No new >=20% attribution to later correctness changes is claimed. AOT and process/RSS measurements are retained separately in the raw file. Repeated AOT compilation was disabled for this replay; setup compile durations are not a compile-speed benchmark.

## Untimed counters

The temporary runtime overlay emits cumulative counters at the three process_time_ns boundaries. Subtract snapshots 2-1 for deep-copy plus checksum. Instrumented CPU times must not be interpreted as performance results.

| Processing phase, 4,000 graphs | Parent | #821 | Main |
|---|---:|---:|---:|
| Integer heap box allocations |0|432,000|284,000|
| Raw-int lookup operations |720,000|360,000|360,000|
| Any-int lookup operations |0|432,000|432,000|
| Raw-int probe slots |868,606|442,217|439,603|
| Any-int probe slots |0|1,063,184|1,060,062|
| Generic dkeyeq calls |0|0|0|

#821 canonicalizes `dict[int, Any]` memo storage, changes integer hashing/table density, and prevents the old typed membership/get fusion. The typed checksum seen-table remains raw. Object-address hash inputs and therefore exact probe totals vary between runs. Main already reduces allocations through lazy identity reuse. A shorter exact-integer probe loop preserves all boxes, table/hashes/probe order and callbacks; it cannot by itself remove the allocation or table-density costs.

## Reproduction

The manifest preserves original absolute paths/provenance. On another host clone the recorded revisions into private checkouts, set the repository/python/llvm/library_path/lock/output fields, place workload.py at sources/dynany_bench.py, and rebuild each compiler with the pinned toolchain (remove verified_existing/path/binary_sha256 to let runner.py create its own worktrees). Use `python3 runner.py manifest-current.json --max-comparisons 1 --max-new-builds 3`. A different host/toolchain starts a new cohort; do not mix medians. Respect the shared lock and foreign-work guard.

For counters, apply `instrument_runtime.py` to each pinned runtime.c in a separate checkout, then build/run the frozen workload with that checkout as PYSTACHY_HOME. Counter instrumentation is temporary and absent from both PRs. `prototype_runtime.py` reconstructs the runtime-only exact-int candidate; --hash is a separate, unvalidated experiment. Early V1 candidate attempts deferred before complete timing batches; the early artifact labeled hash accidentally omitted that edit and supports no conclusion. V2 reconstructs it correctly.

No whole-application, retained-memory, default-on, or full regression-free claim. Both implementation PRs require their stated CI and review gates; the runtime prototype additionally requires measured benefit.
