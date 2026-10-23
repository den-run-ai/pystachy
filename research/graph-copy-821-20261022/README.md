# Graph-copy regression: current replay and memo profile

Research evidence only; do not merge this branch. Maintained guard: PR #869. Runtime experiment: PR #872, closed without merge for lack of benefit. No runtime optimization is accepted by this evidence. Tracked remaining costs: #780.

Frozen input is the original `tools/dynany_bench.py graph 4000`, SHA256 `2546632715f4df66b2953200f1a41c9d52671e4eee416c9d53a9307acc6dd388`; checksum 670230 in CPython/JIT/AOT.

Revisions: parent `f4b9396167e41616707938ca34d99f359a706622`; #821 `185849790523815d0f63ab1a8b33c17549bf31b4`; current main `46fd53536afac60760b15f068641f7f238f964fe`. CPython 3.13.16 and LLVM 18.1.3, CPU 0, private runtime homes/caches, sanitized settings, interleaved processes and shared-host work preflight. Exact source, compiler and toolchain hashes, all samples and load averages are in the raw JSON.

## Current replay

| JIT processing CPU median | Parent | #821 | Main | Main/parent | Main/#821 |
|---|---:|---:|---:|---:|---:|
| Initial five processes |45.942 ms|64.306 ms|66.668 ms|+45.12%|+3.67%|
| Confirmation five |58.148 ms|84.972 ms|80.316 ms|+38.12%|-5.48%|

These are fresh shared-host samples, not pooled with the previous historical campaign. Load drift is visible; retain every outlier. The regression persists directionally on current main, while main-versus-#821 differences are inconclusive. No new >=20% attribution to later correctness changes is claimed. AOT and process/RSS measurements are retained separately in the raw file. Repeated AOT compilation was disabled for this replay; setup compile durations are not a compile-speed benchmark.

## Untimed counters

These are **native AOT** counter profiles. The temporary runtime overlay emits cumulative counters at the three process_time_ns boundaries. Subtract snapshots 2-1 for deep-copy plus checksum. They establish AOT operations and allocation counts, not JIT instruction/allocation counts. Instrumented CPU times must not be interpreted as performance results.

| Processing phase, 4,000 graphs | Parent | #821 | Main |
|---|---:|---:|---:|
| Integer heap box allocations |0|432,000|284,000|
| Raw-int lookup operations |720,000|360,000|360,000|
| Any-int lookup operations |0|432,000|432,000|
| Raw-int probe slots |868,606|442,217|439,603|
| Any-int probe slots |0|1,063,184|1,060,062|
| Generic dkeyeq calls |0|0|0|

#821 canonicalizes `dict[int, Any]` memo storage, changes integer hashing/table density, and prevents the old typed membership/get fusion. The typed checksum seen-table remains raw. Object-address hash inputs and therefore exact probe totals vary between runs. Main already reduces allocations through lazy identity reuse. A shorter exact-integer probe loop preserves all boxes, table/hashes/probe order and callbacks; it cannot by itself remove the allocation or table-density costs.

The source mechanisms are distinct: typed integer tables use the mixed `pys_hash_int` hash and `2 * size` index slots; canonical Any tables use CPython-compatible numeric hashes and `size` index slots. Aligned object IDs therefore encounter more collisions. Per graph, the copy memo performs 54 membership tests, 18 indexed reads and 36 stores; its old typed lowering fused the 18 successful membership/read pairs. The checksum seen-table performs 54 membership tests and 36 stores. At 4,000 graphs this explains 720,000 old combined raw-int operations versus 432,000 boxed memo operations plus 360,000 raw seen-table operations. These structural counts were independently checked under CPython for seeds 0, 1 and 1,000. They identify the changed work without assigning a percentage of elapsed time to any one mechanism.

## AOT instruction profile

Callgrind 3.22.0 measured the same frozen `graph 4000` source. These **whole-program** instruction totals include graph construction, deep-copy/checksum, startup and GC; they differ from the processing-only CPU timer above. Initial parent/main profiles are single runs with verified executable hashes, matching checksum 670230 and no competing build/timing work at either boundary.

| Executed instructions, initial profiles | Parent | Main |
|---|---:|---:|
| Whole program |321,622,429|443,285,844|
| Typed plus generic dict probe loops, self (`dfindi` + `dfindc`) |39,797,530|60,946,161|
| Dynamic hash dispatcher, self (`pys_dyn_hash`) |6,640,000|26,944,000|
| Collector scan, self (`scan`) |51,672,948|95,379,679|
| Collector bookkeeping, self (`collect`) |7,605,144|13,808,105|
| Allocation slow path, self (`gc_slow`) |24,188,595|26,775,408|
| Outermost deep-copy call, inclusive |186,527,989|248,209,788|
| Outermost checksum call, inclusive |92,497,217|153,535,597|

Self counts exclude callees. Inclusive counts contain their callees and overlap the runtime rows; do not add them together. Recursive Callgrind entries with apostrophe suffixes also overlap and are excluded from this table. GC can run under either copy or checksum, so their individual inclusive shares are not stable attribution of the extra work. Main's outermost copy and checksum account for 56.0% and 34.6% of whole-program instructions in this profile. The extra probe/hash and GC work supports the counter diagnosis. The parent-to-main total spans #821 **and later commits** and is not a separately isolated instruction regression attributable only to #821.

## Rejected exact-integer loop

V2 is PR #872 head `a03095f4826a1559ae4d3c55596eb920cc9f1cce`. The local profile built clean source `024d5b35c46f37d59ef7aa867da38332bbd34697` with runtime SHA256 `7cfe8daaf9bb2a084d9a50198a795d59b952ac9bb91a0535a656252bc0fbf6b5`, using the unchanged main compiler. It specializes exact-int probes but retains the original boxes, hashes, layout, probe order and callback fallback. The tested baseline runtime is `46fd5353`; guard-only base `f38555e0fd850f0ef77de0fe6ba9c853b3f7110e` has the same runtime.

Three interleaved AOT instruction pairs used equal-length executable paths, checked hashes/checksums, and quiet pre/post checks. Median results:

| Instructions | Main | V2 | Change |
|---|---:|---:|---:|
| Whole program |443,285,884|445,110,519|+0.412%|
| `dfindc`, self |43,248,781|45,073,416|+4.219%|
| `collect`, inclusive |119,645,038|119,645,038|0%|

The 1,824,635 additional median whole-program instructions equal the `dfindc` increase. V2 removes the earlier duplicated generic loop, shrinking `dfindc` from V1's 2,135 bytes to 1,301, but baseline is 1,044 bytes. These results show no instruction-cost benefit.

The independent [paired CI run 39884117003](https://github.com/den-run-ai/pystachy/actions/runs/39884117003), job `120188170447`, compares base `f38555e0fd850f0ef77de0fe6ba9c853b3f7110e` to synthetic merge `a8882876ab091cff9052c31b2e5da482e38aef8d`. Its three-sample graph-smoke medians are JIT processing **63.327→65.213 ms (+2.98%)** and AOT processing **58.493→61.110 ms (+4.47%)**. The maintained graph-smoke source hash is `a2218d739d4d2b82f59730f03fd7cb60197035b83ac6883bb85428daf86951b6`; it uses the same graph count and processing-only CPU clock but a different output wrapper. Other controls passed. Neither change triggers the suite's unchanged 20%/5 ms confirmation threshold, and no statistically confirmed slowdown is claimed. Together with the instruction result, it is sufficient to reject V2 as an optimization. Do not pool this CI cohort with local historical samples.

CI raw samples are `candidate-ci-perf-smoke.json`; its extracted summary is `candidate-ci-summary.log`. Artifact `12471717919` ZIP SHA256 is `f4c0fa40c1250ee120aff0b594ecdadc59ea3c274270064f2ee6ec4c1a8cf801`. `callgrind-summary.json` retains initial self/inclusive counts, all confirmation samples, compiler/runtime/executable identities and provenance; `callgrind-profiles.tar.gz` contains raw profiles, annotations and original records, without binaries.

## Reproduction

The manifest preserves original absolute paths/provenance. On another host clone the recorded revisions into private checkouts, set the repository/python/llvm/library_path/lock/output fields, place workload.py at sources/dynany_bench.py, and rebuild each compiler with the pinned toolchain (remove verified_existing/path/binary_sha256 to let runner.py create its own worktrees). Use `python3 runner.py manifest-current.json --max-comparisons 1 --max-new-builds 3`. A different host/toolchain starts a new cohort; do not mix medians. Respect the shared lock and foreign-work guard.

For counters, apply `instrument_runtime.py` to each pinned runtime.c in a separate checkout, then build/run the frozen workload with that checkout as PYSTACHY_HOME. Counter instrumentation is temporary and absent from both PRs. `prototype_runtime.py` reconstructs the runtime-only exact-int candidate; --hash is a separate, unvalidated experiment. Early V1 candidate attempts deferred before complete timing batches; the early artifact labeled hash accidentally omitted that edit and supports no conclusion. V2 reconstructs it correctly.

For the V2 instruction comparison, use `reproduce_callgrind.py --help`. It accepts clean main/candidate checkouts, the matching unchanged native compiler, LLVM and Valgrind paths, a shared lock and a new output directory; it rebuilds AOT executables with private caches, uses equal-length executable paths and alternates three profile pairs. Recreate the two checkouts at the recorded revisions before invoking it. Exact instruction totals can change with addresses, collector state and toolchain; retain provenance and check output. No elapsed time printed by a Callgrind-instrumented program is a native performance result.

The next allocation-avoidance experiment must preserve observable integer identity, including a stored user key's comparison method observing or retaining the query object, and preserve callback order, exceptions and mutation/restart behavior. A stack box or a newly boxed substitute passed to user code is not an established safe replacement. No safe allocation reduction is implemented by this work. The separate direct builtin-number hash-dispatch idea has low semantic scope but no measured benefit here; the profile motivates testing it, not accepting it.

No whole-application, retained-memory, default-on, or full regression-free claim. The maintained guard and the rejected runtime experiment have separate outcomes; the underlying allocation/hash/layout costs remain open under #780.
