# Recursion guard tail-sharing follow-up

Status: frozen evidence for the da84d382 checkpoint. Its fresh bootstrap, applicable CI, complete planned performance series, bounded backend attribution, and full local compilation comparison completed before archival. The previously unpublished local validation export, backend profiles, and reproduction controllers are now preserved below. Performance acceptance remained open at this checkpoint; subsequent PR source changes require separately identified evidence.

The evaluated implementation is former PR #996 head `da84d382ff83f09e46d4ef104e62e6f64e9c37c1`, tree `903a72dce156018f83f69f1e8b4d74a6f14e99dd`, based on main `06e3ad5d08514ba31fb231fe4636a962fe6578e3`. Its parent checkpoint is `aaec00cc81a862a2b29c117003e7c9cc73e1a3c1`, tree `2dd336a2a8f71d9a2c36d1fd233af24fee81c2a1`. This separate research branch preserves evidence and must not be merged into the source PR.

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

The local startup series is complete below. The later da84d382 sections record the subsequently completed kernel/count/compilation measurements, focused native fixtures, and full 3,918-case comparison. All applicable aaec00cc CI checks completed: **59 successful and two expected skips**, with no failures or pending jobs. The correctness workflow completed 34/34 jobs and 54/54 aggregate verification steps across 31 groups. Coverage completed 19 successful jobs and its expected main-only badge skip. Lint, installation, packaging and smoke passed. The skips are main-only coverage publication and fork-only DCO. PR #996 remained draft and unmerged at that checkpoint.

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

Before publication, the integrated source passed 198 typed-IR tests, seven function-summary tests, 107 compiler-state tests, 11 repository-hygiene tests, Ruff and diff checks. Fresh full self-hosting subsequently passed as recorded below. Final-source CI and the full local comparison subsequently completed successfully; the single hosted experimental build is not relabeled as that final validation.

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

Fresh final preparation also regenerated all six benchmark artifacts and verified literal raw LLVM, optimized JIT bitcode and AOT executable equality with aaec00cc. It retained and rehashed all 84 preceding artifacts, verified the actual normal-driver runtime descriptor and input/pipeline, and preserved earlier failed preparation records. Final counts, kernel timings, compilation samples, and the local correctness comparison subsequently completed as recorded below.

## Completed final JSON measurement series

The final record is `tail-final-json-intel.json` (384,956 bytes, SHA256 `adddef35dede86bf36d3b064dee9fb09bed4a2d2dd0e4076030960cf77b37595`). All preparation/count/timing/compile phases passed their source, native-binary, artifact, checksum and full Git identity checks. It compares freshly bootstrapped main06e3ad5d, pre-tail region head eca993b9, and final da84d382 on the restored Intel host. Main/eca prepared artifacts are explicitly reused after rehashing; final artifacts are regenerated. This is a new measurement series, not a relabeling of the AMD results.

The four elapsed labels represent three unique source files. Six process orders cover all permutations of the three variants, with each variant occupying each position twice. Each of the 144 processes performs one warm-up and seven measured kernel calls (1,008 measured calls); warmed labels perform four additional untimed calls. Summaries use the median within each process and then across process medians. The original-size input is 2,000 iterations, and long/file labels use 20,000. The scoped-file program creates, reads and explicitly closes its native files before timing; this tests optimization eligibility of a file-using program, not file-I/O throughput.

### Whole-kernel instruction counts

There are 12 observations: two JSON cases, three variants, JIT/AOT. Each observation covers eight kernel calls at 2,000 iterations, including the warm-up; runtime and GC work are included, while compiler, timers and printing are excluded. JIT uses client markers with every non-entry raw function body verified unchanged. AOT collects at the unmodified `f.kernel` entry/return and verifies all eight returns. Raw-body equality does not prove identical downstream register allocation or machine-code layout. No hardware PMU was available.

| Kernel / mode | Main instructions | eca instructions | Final instructions | Final vs main |
|---|---:|---:|---:|---:|
| JSON JIT | 572,272,000 | 599,307,331 | 598,872,478 | +4.65% |
| JSON AOT | 526,398,962 | 536,695,581 | 536,695,516 | +1.96% |
| Scoped-file JSON JIT | 571,962,991 | 599,415,084 | 598,921,391 | +4.71% |
| Scoped-file JSON AOT | 526,452,796 | 536,749,376 | 536,749,376 | +1.96% |

The tail-sharing follow-up produces a small additional JIT instruction reduction over eca (about 0.07–0.08% of its count); AOT counts are essentially unchanged. The preceding bounded-region optimization remains the substantive reduction in repeated-call overhead. Ordinary and object probes are byte-identical to eca in raw LLVM, optimized JIT bitcode and AOT executable bytes under this toolchain; their earlier elapsed results remain historical and are not retimed or relabeled here.

### Kernel elapsed results

These are ratios of variant medians relative to current main, not statistical performance guarantees:

| Label | eca JIT | Final JIT | eca AOT | Final AOT |
|---|---:|---:|---:|---:|
| Original-size JSON | +2.10% | -0.02% | +0.51% | -1.29% |
| Warmed original-size JSON | -2.00% | +0.73% | +5.61% | -3.86% |
| Warmed longer JSON | +1.75% | -0.74% | +7.13% | +0.82% |
| Scoped-file longer JSON | +3.76% | +2.34% | +3.68% | +3.57% |

Paired rounds expose uncertainty hidden by a single ratio of medians. For original-size AOT, the aggregate −1.29% accompanies a **+3.24% median paired ratio**, four of six slower pairs and a −11.84% to +29.24% paired range. For warmed-long AOT, aggregate +0.82% accompanies **+3.51% median paired overhead**, five of six slower pairs and a −15.81% to +114.84% range. The large unfavorable observation is retained. Small apparent speedups are inconclusive, and these results do not establish acceptable elapsed overhead. All process records, seven-sample vectors, round order and hashes remain in the dataset.

### Compilation samples

The 72 observations cover four labels × three variants × IR/AOT-build stages × three rotated samples. Each emitted module/executable is checked against the prepared artifact hash. Times below are medians with full sample ranges, in seconds:

| Label / stage | Main | eca | Final |
|---|---:|---:|---:|
| Original-size JSON / IR emission | 0.039 (0.036–0.061) | 0.046 (0.041–0.052) | 0.039 (0.036–0.046) |
| Original-size JSON / AOT build | 2.653 (2.629–3.774) | 2.722 (2.690–2.725) | 2.691 (2.661–2.870) |
| Warmed original-size JSON / IR emission | 0.039 (0.039–0.051) | 0.047 (0.042–0.061) | 0.045 (0.042–0.046) |
| Warmed original-size JSON / AOT build | 2.800 (2.633–2.890) | 3.359 (2.940–3.952) | 3.049 (2.802–3.285) |
| Warmed longer JSON / IR emission | 0.043 (0.042–0.045) | 0.053 (0.043–0.055) | 0.059 (0.056–0.060) |
| Warmed longer JSON / AOT build | 2.685 (2.582–2.778) | 3.014 (2.817–3.380) | 2.691 (2.681–3.753) |
| Scoped-file longer JSON / IR emission | 0.041 (0.040–0.054) | 0.047 (0.047–0.048) | 0.053 (0.044–0.053) |
| Scoped-file longer JSON / AOT build | 2.816 (2.737–2.820) | 2.872 (2.856–2.958) | 2.865 (2.804–3.156) |

The warmed-short and warmed-long labels compile the same source into identical artifacts; their different medians demonstrate why three samples on this shared host cannot establish precise compilation-speed changes. The separately controlled early-rejection experiment measures its narrow frontend change against aaec, not against unguarded main and not the entire JIT startup path.

## Completed final-head CI

All 61 checks on da84d382 resolved: **59 successful, two expected skips, no failures or pending jobs**. The [correctness workflow](https://github.com/den-run-ai/pystachy/actions/runs/41220634706) completed 34/34 jobs; its aggregate reports 54 checks across 31 groups. Coverage, Lint, Installation, Packages and performance smoke completed. The expected skips are fork-only DCO and main-only coverage badge publication. PR #996 remains draft and unmerged.

The exact Coverage/Lint record is `tail-ci-coverage-lint-da84d382.json`, SHA256 `2b1f2250d6d7b21d5158672ecba8bcaade081bf0395347a95e8f62a1291f6644`. Every successful job's checkout identifies the verified synthetic merge tree. Both native and hosted coverage corpora passed 6,134 mode executions; native/hosted FFI passed 110/145, with the documented hosted py_coerce conditional skip. Typed IR passed 198 tests, function summaries seven, compiler state 107 and smoke harness 24; Mypy checked 48 source files and all 1,943 recordings matched.

Hosted coverage is 96.0% statements/92.6% branches; native runtime coverage is 95.5% lines/87.5% branches, exactly matching aaec. Changed-code gap lists are unchanged. Existing compiler gaps include defensive rejection and init-to-call rewrite paths. C recursion helper bodies remain uncovered because normal native lowering uses the program module's inline LLVM helpers; C coverage does not measure those emitted operations. Coverage is not a proof of every guard path.

The exact correctness aggregate record is `tail-ci-correctness-da84d382.json` (SHA256 `4df44515855e4c429349601df64f8bd9044bfea5f33400418fb0c71b13e27aef`). Its verified ZIP, JSON and 61 retained raw-log hashes support native/optimization-disabled/Python-free totals of 6,134 mode executions each; UBSan 8,162; GC JIT and GC AOT 4,081 each; runtime-cache 66 native + 68 hosted = 134. The new-head regex job built the native stage-2 compiler and verified four upstream methods across CPython, native JIT and AOT. These totals are mode/check counts, not a count of unique programs.

## Completed local validation and backend attribution at da84d382

The [archived evidence directory](../../bench/recursion/archive-da84/README.md) publishes the completed records that were retained but unpublished at handoff. Its [publication manifest](../../bench/recursion/archive-da84/publication-manifest.json) binds every copied file to its original path, size, and hash. This is publication of frozen evidence, without new compiler or benchmark execution and without advancing the evaluated source.

The complete local comparison covers **3,918 cases**: both main and da84d382 accept 2,134 and reject 1,784, with **zero changed exit statuses, new acceptances, or new rejections**. Of the accepted modules, 2,133 have intentional raw LLVM differences and one is identical. The export retains every raw diagnostic and the audited filename mappings: 61 diagnostics have checkout-path changes, including 45 nested call locations. Runtime IR is identical. This establishes compilation compatibility for the recorded corpus; it does not alone prove runtime equivalence.

Twenty focused fixtures passed **150 native executions** across normal JIT/AOT, disabled leaf/region optimization, disabled user inlining, and GC stress configurations. The fixture list includes exact-limit failure and recovery, contexts/unwind, generators, dynamic calls, regex fallback, scoped files, and weakref controls. Full source inventories, bootstrap bindings, every comparison result, diagnostic bytes, and raw IR/archive hashes are in [the lossless validation export](../../bench/recursion/archive-da84/validation/validation-final-da84.json.gz). Its decompressed 7,807,297 bytes have SHA256 `1560bc34b2b404106eb51e4601b084edf1a9777336a285bc811c5330939cf566`.

The actual-driver backend profile compiled the mixed-text module and ran `fnmatch 1000`, with CPython output parity and matching captured runtime descriptor bytes. Each row is one instrumented whole-tool observation per variant:

| Process | Main instructions | da84d382 instructions |
|---|---:|---:|
| LLVM `opt` | 1,672,852,665 | 2,195,365,411 |
| LLVM `lli` | 8,327,345,252 | 9,474,607,734 |
| Sum of the two disjoint processes | 10,000,197,917 | 11,669,973,145 |

The combined instruction increase is **16.70%**. LLVM's always-inline pass accounts for 318,912,600 inclusive instructions, approximately 61% of the additional `opt` work. Named machine-code generation work also increases. Inclusive rows overlap and must not be added; attribution does not measure the savings from removing a pass. Whole `lli` includes execution, runtime/GC, and teardown as well as code generation. These are instruction observations, not an elapsed acceptance series, and exclude the native frontend/driver.

The [curated profile](../../bench/recursion/archive-da84/backend-attribution/curated.json) and [complete compressed backend record](../../bench/recursion/archive-da84/backend-attribution/backend-attribution-da84-full.json.gz) retain the exact pipelines, source/tool/input identities, normal controls, and limitations. The latter decompresses to 7,754,882 bytes with SHA256 `5374af1a1bada3138183f33dc513ef55b128de80f802dd61994e16f5301bf352`.

Read the [original reproduction notes](../../bench/recursion/archive-da84/reproduction/README.md) before using the copied controllers. They have ordered dependencies and original-workspace path assumptions; the source/toolchain/cache/raw-IR archives remain necessary for exact reconstruction. The older missing startup diagnostic remains missing. This publication does not fill its unrecorded samples or close performance acceptance.
