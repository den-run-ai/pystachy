# Recursion guard tail-sharing follow-up

Status: the aaec00cc checkpoint completed all applicable CI. A further exact-output frontend fix is published as da84d382; its fresh bootstrap passed, CI is being verified, and kernel measurements/full comparison are in progress. Performance acceptance remains open.

The current reviewed implementation is PR #996 head `da84d382ff83f09e46d4ef104e62e6f64e9c37c1`, tree `903a72dce156018f83f69f1e8b4d74a6f14e99dd`, based on main `06e3ad5d08514ba31fb231fe4636a962fe6578e3`. Its parent checkpoint is `aaec00cc81a862a2b29c117003e7c9cc73e1a3c1`, tree `2dd336a2a8f71d9a2c36d1fd233af24fee81c2a1`. This separate branch preserves evidence without adding raw evaluations to the PR.

## Implemented changes

The initial region optimization removes repeated entry checks and bookkeeping only inside a bounded private graph selected by a non-raising remaining-depth test. Insufficient depth executes the original guarded body. The file eligibility proof permits immediately rooted scoped files; unmanaged files, weakrefs, exit hooks and embedding boundaries remain conservative.

The latest change shares equivalent private partial-region return tails before mandatory inlining. It requires the same slot load, direct private child call, return, types and external operands, permits alpha-renaming only of the two local results, and excludes special control-flow/metadata uses. It preserves both the guarded fallback and the original proof/budget. It adds 89 source lines; total compiler/runtime growth relative to 993fb17e is 782 net lines.

A separate smoke-harness fix checkpoints completed measurements atomically, preserves incomplete/error states and uses the repository's existing 15-minute job ceiling. Workloads, sample counts, warning criteria and per-command timeouts are unchanged.

## Fresh recovery and provenance

A scratch-workspace cleanup removed local tools and uncommitted diagnostic files after an earlier successful bootstrap. Source commits, existing benchmark datasets, and CI artifacts survived. The exact 85,660-byte startup diagnostic export was lost; a later report must distinguish partial transcript recovery from a complete raw dataset. Existing AMD EPYC 9V74 results remain historical.

The restored local environment uses Intel Xeon Platinum 8573C, CPython 3.13.16, LLVM/Clang 18.1.3, and Valgrind 3.22.0. The toolchain manifest records exact distributions and hashes; binary identity with the old toolchain is not asserted. New comparisons rebuild all participating variants on this host.

## Completed aaec00cc checkpoint

A fresh local bootstrap completed successfully in 334.3203 seconds with an unchanged 137-file source snapshot. All three native binaries are byte-identical (SHA256 `066ca28a41256c32bb4962b6dfd82a4a8ce883e963ce4557a4be6aca9ad935e3`). All three compiler IR modules are identical: 805,028 lines, SHA256 `f918a33a73bb3f8164b986089534fa1370c91272649017db54a41527a4f56409`. All three runtime modules are identical: 18,805 lines, SHA256 `940a694da5ea93214d1308a8eb635b47d8d0a9d4256c63d084c24f5099f8aa5f`, also matching the prior runtime IR.

The aaec00cc CI performance smoke completed successfully with all 11 workloads, a complete schema-2 JSON report, and no warning-triggering metrics. Its AMD EPYC 7763 runner observed whole-JIT-process overhead of 19.31% for fnmatch and 19.46% for mixed JSON versus main; corresponding JIT kernel changes were 2.45% and 4.97%. Neither case triggered confirmation because the initial process ratio was below 20%. An advisory pass is not performance acceptance.

- [CI smoke run](https://github.com/den-run-ai/pystachy/actions/runs/41214277702)
- [Verified complete artifact](https://github.com/den-run-ai/pystachy/actions/runs/41214277702/artifacts/13047717899), ZIP SHA256 `59f096079b53c0ca9184988c83ea80208ca165f349cfb08b1c571aabe845a222`.
- JSON SHA256 `936d3705f5847c98cf59cb0978c3fa04576d9dface9d5d51464a8e2e8cdb477d`.

The local startup series is complete below. Fresh local kernel/count/compilation measurements, focused native fixtures and a complete 3,918-case compilation comparison remain pending. All applicable aaec00cc CI checks completed: **59 successful and two expected skips**, with no failures or pending jobs. The correctness workflow completed 34/34 jobs and 54/54 aggregate verification steps across 31 groups. Coverage completed 19 successful jobs and its expected main-only badge skip. Lint, installation, packaging and smoke passed. The skips are main-only coverage publication and fork-only DCO. PR #996 remains draft and unmerged.

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

The fnmatch initial ranges overlap, and its initial tail-sharing improvement did not persist in confirmation. JSON triggered no confirmation and showed no clear tail-sharing improvement. Consequently **this complete native series does not establish a startup speedup from tail sharing alone**. The reduced optimized IR is real; a robust elapsed benefit is not established. The remaining startup overhead versus main motivated the separately identified whole-region budget experiment below. It was not adopted; the published PR source retains the original 2048 whole-closure budget.

## Generated-artifact equivalence

The six-case preparation is complete. Across freshly built eca and aaec native compilers, ordinary calls and the object-method loop are **byte-identical in raw LLVM, optimized JIT bitcode and AOT executable bytes**. The short JSON, warmed short JSON, warmed long JSON and scoped-file JSON labels differ and require fresh kernel measurements. Native and hosted emission agree for every prepared pair, and all checksum runs pass.

The actual normal-driver capture proves the constructed JIT input has the identical target directives, raw program and OBJHOOKS; the actual opt pipeline and `-dlopen=/dev/fd/8` invocation are retained. The inherited descriptor holds an executable regular ELF ET_DYN object with bytes matching the normal runtime cache. An initial preparation assertion incorrectly required its pathname to remain present and end in `.so`; the driver intentionally unlinks the opened temporary library. That failed attempt is preserved. The corrected check reads and hashes the open descriptor, and a narrow resume completed the remaining proof and bitcode comparison after revalidating all prepared source/artifact hashes. No source changed and no completed builds were silently repeated.

The complete preparation record is `tail-artifact-equivalence-intel.json` (SHA256 `199dc36d7fbadfcb5e6d470b3cec52f9d016230418ae7ca4fbbd56bb7670e724`). Additional datasets preserve exact fresh main/eca bootstrap records and the Intel-host hardware-counter probe. A self-only `perf_event_open` request returns `ENOENT`; no usable hardware counter was exposed, and no privilege escalation was attempted for profiling. Callgrind remains the instruction-count method.

`tail-pre-cleanup-partial-recovery.json` contains only exact vectors retained in earlier conversation output. It explicitly identifies missing confirmation/raw records and does not claim to recover the lost 85,660-byte export or its hash.

## Rejected smaller whole-region budget

A separate worktree changed only the three whole-region 2048 limits to 512. Partial-region limits and both aggregate budgets were unchanged. Its independently constructed nested-call test distinguishes transitive closure size from each function's own size and fails against the old boundary as expected. A single native hosted build passed; all six benchmark raw modules remained unchanged, but the mixed-text module fell from 81,576 to 77,814 lines and from 33 to 13 whole-region private functions. All nine partial private functions remained.

The complete native experiment retained six preplanned alternating pairs in two three-pair batches (84 full-process records). It did **not** show a consistent startup benefit:

| Metric | Candidate/current, first batch | Candidate/current, replication |
|---|---:|---:|
| fnmatch JIT process | 1.0083 | 1.0461 |
| mixed JSON JIT process | 0.9005 | 1.0895 |
| fnmatch AOT build | 1.0519 | 0.9174 |

The directions conflict across batches; the full six-pair JIT ratio ranges were 0.617–1.243 for fnmatch and 0.736–1.153 for JSON. Absolute host timings also drifted, without a demonstrated cause. Reducing coverage on this evidence would be unjustified. This experiment is **not part of the PR**.

Exact dataset: `tail-cap512-experiment-intel.json`, SHA256 `d1e62e4b1fba97c53f6bdccf858553e43b6cd1805fe78e772d1e790e08d26454`. Source patch, harness identity, single-build provenance and all initial/replication records are retained.

## Native frontend profile

One pinned Callgrind observation measured the complete native `ir` command for mixed text at aaec00cc, with literal output equality to the uninstrumented module. It counted **2,836,884,329 instructions**. Whole-region analysis accounted for 91,565,471 inclusive instructions (3.23%); partial-region analysis for 221,453,976 (7.81%); leaf analysis for 153,271,709 (5.40%). Inclusive values can overlap and allocate/collect on behalf of callers, so they are not independent fractions of full-JIT startup.

The return-path analysis's inclusive count was 131,332,437, mostly through allocation; the profile does not establish that a graph algorithm alone dominates. Effect-summary updates were only 457,583 instructions (0.016%), giving no reason to redesign that machinery. Runtime equality/lookup and collector work also dominate flat rows. The full 1,636 positive function rows and selected edges are in `tail-frontend-profile-intel.json`, SHA256 `da7a39253f835f73e4c871b1deaf3f2bc78f94822507e5e58f8afb8b03808d19`.

This is frontend IR emission, not LLVM optimization or the entire JIT process. There is no hardware-PMU attribution, and inlining limits per-symbol interpretation.

## Adopted early rejection: da84d382

The partial pass already rejected roots whose snapshotted weight exceeded 768 operations/slots, but only after building successors, return-path information and observer propagation. The two-line compiler change moves that same unconditional rejection ahead of those analyses. It changes no budget, proof, eligible function, fallback body or generated-program semantics. The existing boundary test now checks that an oversized root never invokes the two analysis helpers, and that an eligible root still invokes both and receives its private version. The extended test fails on the former analysis order.

In mixed text, seven roots already destined for rejection contained **23,679 typed operations, 4,172 CFG blocks and 6,156 CFG edges**. The change reduces actual root successor/returning analyses from 121 to 114 calls, analyzed blocks from 7,254 to 3,082 and edges from 9,908 to 3,752. The 64 child-analysis calls are unchanged. All 42 private function selections (33 whole, nine partial) remain identical.

Own-home emission initially differed only in a library pathname within an ImportError constant. That attempt is preserved. After verifying all consumed inputs and the symmetric library/runtime file sets, a common identical library/runtime home allowed **literal equality across all seven labels**: mixed text and the six benchmark probes. Both native and hosted compilers agree with aaec. No generic text normalization was used.

The separate native experiment performed one hosted build (150.49 seconds), verified all seven modules and compared one complete Callgrind frontend observation with the existing aaec observation:

| Observation | aaec00cc | Early rejection | Change |
|---|---:|---:|---:|
| Native IR-emission instructions | 2,836,884,329 | 2,784,618,256 | −1.8424% |
| Six-pair IR-emission median ratio | — | 0.9463508 | −5.36% |
| Median paired ratio | — | 0.9405166 | −5.95% |

Five of six pairs favored the candidate; paired ratios ranged from 0.91908 to 1.00163. Current observations ranged from 0.506 to 0.544 seconds; candidate observations from 0.486 to 0.516 seconds. These are small descriptive samples on the shared Intel host. The absolute instruction reduction is 52,266,073. The larger decrease in one helper's inclusive allocation/GC attribution is **not** an equivalent total GC saving; the whole-process total is the relevant count. A missing separately named partial-pass symbol in the candidate profile reflects inlining/attribution limits, not zero partial work.

This removes demonstrated redundant frontend work. It does **not** establish a whole-JIT startup improvement or resolve elapsed-performance acceptance.

Exact hosted proof: `tail-early-rejection-proof.json`, SHA256 `dc7f5240868791a7418f3ad4e6a9b6a5b8bdc60082374ba352c150bd901600c0`. Exact native experiment: `tail-early-rejection-native-intel.json`, SHA256 `cb181e48ad3c730ebf7a3b1f56aac01e695e07c59d7a2d03268ce7afd7f9ada2`.

Before publication, the integrated source passed 198 typed-IR tests, seven function-summary tests, 107 compiler-state tests, 11 repository-hygiene tests, Ruff and diff checks. Fresh full self-hosting subsequently passed as recorded below. Final-source CI is being verified and the full local comparison remains pending; the single hosted experimental build is not relabeled as that final validation.

## Final-source bootstrap and CI smoke

The clean da84d382 checkout passed a full fresh `make` bootstrap in 347.7206 seconds, with its 137-file source snapshot unchanged. All three native binaries have SHA256 `8ee9b55b99c85a1406198643a5405d6e58ef566ec5896f6af3b03daf478b3f75`, also equal to the separately built experimental native compiler. All three compiler IR stages are **805,049 lines**, SHA256 `ed51d1f07ca2e47eb53646e57a0543bcbe41bd121abbf6b1eab3a0ddca74b709`. All three runtime IR stages remain **18,805 lines**, SHA256 `940a694da5ea93214d1308a8eb635b47d8d0a9d4256c63d084c24f5099f8aa5f`. CI independently produced those exact compiler/runtime IR hashes.

The final-head [CI performance smoke](https://github.com/den-run-ai/pystachy/actions/runs/41220634754) completed successfully in approximately eight minutes and preserved all 11 workloads, including three confirmation batches. It tested synthetic merge `093436389af8356bb110b6b0b49e33d6b6c3d189`, whose tree exactly equals da84d382 and whose parents are main06e3ad5d and da84d382. This runner used AMD EPYC 9V74, CPython 3.13.16, LLVM/Clang 18.1.3 (Ubuntu 1ubuntu1), pinned CPU 0. It is a separate runner/series from both the previous CI artifact and the restored Intel measurements.

| Workload | Initial whole-JIT process | Confirmation process | Initial JIT kernel | Confirmation kernel |
|---|---:|---:|---:|---:|
| fnmatch | +23.73% | +18.71% | +2.22% | +1.71% |
| mixed JSON | +20.31% | +18.75% | +2.21% | +3.50% |
| repair scan | +20.42% | +18.39% | −0.72% | +2.09% |

Each process comparison had non-overlapping base/head ranges in both batches. The advisory classifier calls them **unconfirmed** because the confirmation ratios fall below its 20% trigger. This label does not establish parity or remove the material startup cost. The fnmatch AOT build ratio was +13.89% initially and +13.17% in confirmation. There are no warning-classified metrics, but **performance acceptance remains open**.

The complete artifact is [13049892239](https://github.com/den-run-ai/pystachy/actions/runs/41220634754/artifacts/13049892239). ZIP SHA256: `95fb310fdd76ae3dbb212fdb5758a41cd831c6d4254fbb76989cb7225a261c71`. Exact JSON is `tail-ci-smoke-da84d382.json`, 61,675 bytes, SHA256 `401deeac72292dbc79b447f5b51fad7141009a33c2b6442156d15e14ef454391`. The bootstrap record is `tail-bootstrap-da84d382.json`, SHA256 `043fa1d1b5797a832deffd7b6a1841fff8982558cd4d07cb693021ca31b3c0cf`.

Fresh final preparation also regenerated all six benchmark artifacts and verified literal raw LLVM, optimized JIT bitcode and AOT executable equality with aaec00cc. It retained and rehashed all 84 preceding artifacts, verified the actual normal-driver runtime descriptor and input/pipeline, and preserved earlier failed preparation records. Final counts, kernel timings, compilation samples and local correctness comparison remain in progress.
