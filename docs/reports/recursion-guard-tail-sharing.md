# Recursion guard tail-sharing follow-up

Status: all current-head CI passed; fresh local measurements and full comparison are in progress. Performance acceptance remains open.

The reviewed implementation is PR #996 head `aaec00cc81a862a2b29c117003e7c9cc73e1a3c1`, tree `2dd336a2a8f71d9a2c36d1fd233af24fee81c2a1`, based on main `06e3ad5d08514ba31fb231fe4636a962fe6578e3`. This evidence branch preserves checkpoints without changing the reviewed PR source.

## Implemented changes

The initial region optimization removes repeated entry checks and bookkeeping only inside a bounded private graph selected by a non-raising remaining-depth test. Insufficient depth executes the original guarded body. The file eligibility proof permits immediately rooted scoped files; unmanaged files, weakrefs, exit hooks and embedding boundaries remain conservative.

The latest change shares equivalent private partial-region return tails before mandatory inlining. It requires the same slot load, direct private child call, return, types and external operands, permits alpha-renaming only of the two local results, and excludes special control-flow/metadata uses. It preserves both the guarded fallback and the original proof/budget. It adds 89 source lines; total compiler/runtime growth relative to 993fb17e is 782 net lines.

A separate smoke-harness fix checkpoints completed measurements atomically, preserves incomplete/error states and uses the repository's existing 15-minute job ceiling. Workloads, sample counts, warning criteria and per-command timeouts are unchanged.

## Fresh recovery and provenance

A scratch-workspace cleanup removed local tools and uncommitted diagnostic files after an earlier successful bootstrap. Source commits, existing benchmark datasets, and CI artifacts survived. The exact 85,660-byte startup diagnostic export was lost; a later report must distinguish partial transcript recovery from a complete raw dataset. Existing AMD EPYC 9V74 results remain historical.

The restored local environment uses Intel Xeon Platinum 8573C, CPython 3.13.16, LLVM/Clang 18.1.3, and Valgrind 3.22.0. The toolchain manifest records exact distributions and hashes; binary identity with the old toolchain is not asserted. New comparisons rebuild all participating variants on this host.

## Completed checkpoint

A fresh local bootstrap completed successfully in 334.3203 seconds with an unchanged 137-file source snapshot. All three native binaries are byte-identical (SHA256 `066ca28a41256c32bb4962b6dfd82a4a8ce883e963ce4557a4be6aca9ad935e3`). All three compiler IR modules are identical: 805,028 lines, SHA256 `f918a33a73bb3f8164b986089534fa1370c91272649017db54a41527a4f56409`. All three runtime modules are identical: 18,805 lines, SHA256 `940a694da5ea93214d1308a8eb635b47d8d0a9d4256c63d084c24f5099f8aa5f`, also matching the prior runtime IR.

Current-head CI performance smoke completed successfully with all 11 workloads, a complete schema-2 JSON report, and no warning-triggering metrics. Its AMD EPYC 7763 runner observed whole-JIT-process overhead of 19.31% for fnmatch and 19.46% for mixed JSON versus main; corresponding JIT kernel changes were 2.45% and 4.97%. Neither case triggered confirmation because the initial process ratio was below 20%. An advisory pass is not performance acceptance.

- [CI smoke run](https://github.com/den-run-ai/pystachy/actions/runs/41214277702)
- [Verified complete artifact](https://github.com/den-run-ai/pystachy/actions/runs/41214277702/artifacts/13047717899), ZIP SHA256 `59f096079b53c0ca9184988c83ea80208ca165f349cfb08b1c571aabe845a222`.
- JSON SHA256 `936d3705f5847c98cf59cb0978c3fa04576d9dface9d5d51464a8e2e8cdb477d`.

Fresh local startup/kernel/count/compilation measurements, focused native fixtures and a complete 3,918-case compilation comparison are still pending. All applicable current-head CI checks have now completed: **59 successful and two expected skips**, with no failures or pending jobs. The correctness workflow completed 34/34 jobs and 54/54 aggregate verification steps across 31 groups. Coverage completed 19 successful jobs and its expected main-only badge skip. Lint, installation, packaging and smoke passed. The skips are main-only coverage publication and fork-only DCO. PR #996 remains draft and unmerged.

## Exact CI accounting

The two adjacent `tail-ci-correctness-aaec00cc.json` and `tail-ci-coverage-lint-aaec00cc.json` datasets preserve source/merge/tree identities, all expected jobs, aggregate artifact IDs/digests and raw-log hashes. Native, optimization-disabled and Python-free modes each passed 6,134 executions; UBSan passed 8,162; GC JIT and GC AOT each passed 4,081 including their stressed compiler samples; runtime-cache passed 134. The IR contract checked 2,134 programs; GC IR comparison covered 3,837 cases plus 250 parser checks. These are mode/check counts, not unique programs. Typed IR passed 198 tests, function summaries 7, compiler state 107, and smoke harness 24. Mypy checked 48 source files; 1,943 CPython recordings had no failures.

The CI compiler and runtime IR hashes equal the fresh local fixed points listed above. CI uses synthetic merge `664c6c5d23f431a01c719f021d93027f09f09ffb`, whose tree exactly equals the published head and whose parents are main and aaec. The different local/CI native binary toolchain provenance is retained.

## Fresh local three-variant startup series

A complete same-host comparison used freshly bootstrapped native compilers for main, pre-tail region head eca993b9, and tail-sharing head aaec00cc. The harness preserves the original smoke classifiers and workloads but uses a disclosed three-variant rotating schedule: three samples per variant, with three reverse-rotated confirmation samples for all variants when any comparison triggers the original criterion. This is not the exact two-variant CI schedule. Output parity, clean source identities and native-binary hashes were checked; all initial and confirmation records are retained in `tail-native-startup-intel.json` (SHA256 `cb65e9912cde0dd9e6bae3fcd46ba6f9c037156c5dca72433398bc63b378133e`).

| Case / batch | Main JIT process median | eca median | aaec median | aaec vs main | aaec vs eca |
|---|---:|---:|---:|---:|---:|
| fnmatch initial | 3.121756 s | 3.814543 s | 3.618984 s | +15.93% | -5.13% |
| fnmatch confirmation | 2.921667 s | 3.664718 s | 3.664731 s | +25.43% | +0.0003% |
| mixed JSON initial | 3.093792 s | 3.629913 s | 3.653249 s | +18.08% | +0.64% |

The fnmatch initial ranges overlap, and its initial tail-sharing improvement did not persist in confirmation. JSON triggered no confirmation and showed no clear tail-sharing improvement. Consequently **this complete native series does not establish a startup speedup from tail sharing alone**. The reduced optimized IR is real; a robust elapsed benefit is not established. The remaining startup overhead versus main motivates a separately identified whole-region budget experiment. Its results are pending, and the released PR source still uses the original 2048 whole-closure budget.
