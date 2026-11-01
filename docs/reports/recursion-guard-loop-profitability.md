# Recursion guard loop profitability: prototype decision

## Decision and source identities

PR #996 now contains a narrower profitability rule for recursion-region versioning. It reduces measured instruction counts and generated code without changing the runtime ABI or imposing another CPython compatibility restriction. **It does not establish an elapsed-time improvement. The PR remains draft, with performance acceptance open.** The alternative scalar-depth implementation was prototyped and rejected because it regressed the object-call control.

| Role | Source revision |
|---|---|
| Main | `07b26e02425d023288ed95a9d2a5077be5aeb45e` |
| Previous PR / baseline | `ea68529b8a590eb8f3df7200b857e1d16becd7a3` |
| Rejected scalar prototype | ea685 plus the preserved, unapplied scalar patch |
| First policy checkpoint | `1ff5efe4c4425b3728e138fa05a44856202fdea5` |
| Final policy / current PR | `44b638bbf8df1835b67bebda0468d65374569c71` |

The final source tree is `a1eddfe2c43d368b5c48ac79798501d8d7add552`. Its complete 8,191-entry published tree, including paths, modes and object IDs, matches the staged local tree. Final CI tests synthetic merge `b20d3720ed557a6934e6ac10a6287a5610d2fc1f`, with that same tree and exact parents main07b and head44b. The first checkpoint's failures and measurements remain separate historical evidence.

## Change and reason

The former profitability rule accepted a loop when a counted child call existed somewhere in its control-flow cycle. In the measured fnmatch workload, that selected the regex `charset` helper even though its exercised path made no child calls. The selector and specialized body still ran on every invocation.

The final rule requires at least one real loop with a counted child call on every continuing path back to its head before its recorded exit. Calls in the loop condition qualify; a call-free `continue` disqualifies that loop; paths through the exit need no call. A loop record with no remaining cycle cannot justify versioning. Successful-child caching uses the same rule, counting only eligible leaf calls. Existing finite-depth proofs, guarded fallback, callable addresses, exception order and lifetime exclusions remain in force.

The first implementation followed paths through an inner loop's exit and back through an enclosing loop. That incorrectly rejected useful nested-loop regions in the existing `index_key` fixture. CI caught the change in `tests/ir/index_key.calls`. Commit 44b stops that reachability walk at the recorded exit and adds nested-loop positive and conditional/continue controls. The existing golden is unchanged and passes again. This is a conservative profitability test, not a general loop reconstruction algorithm; unusual control flow can still decline an optimization safely.

Seven new hosted test methods cover the original and nested boundaries. Only five files change relative to ea685: the optimizer, two test modules and two compiler contract documents. There is no new IR operation, hidden argument, runtime setting or compatibility restriction. Freed clone budgets can alter later choices, so generated private functions need not be a literal subset of previous output.

## Profile findings and AOT instructions

The mixed text benchmark's fnmatch mode includes cached matching and fresh regex translation/compilation on every outer iteration. It is not a matching-only microbenchmark. AOT Callgrind profiles use `n=10000` and cover the whole process.

The baseline `charset` family accounts for 67,853,568 of 107,973,697 excess instructions versus main, or 62.84%. It executes 1,280,256 times, with no child calls on this measured input. Disassembly and instruction-address counts attribute 30 extra instructions per call to the selector/wrapper and 23 to its specialized body, including predicates introduced after inlining. The final policy removes 50 of those 53 instructions per call.

| AOT fnmatch measure | Main | ea685 | Scalar prototype | Final 44b |
|---|---:|---:|---:|---:|
| Whole-process instructions | 1,911,425,777 | 2,019,399,474 | 1,951,216,846 | 1,954,056,920 |
| `charset` family instructions | 163,512,696 | 231,366,264 | 163,512,696 | 167,353,464 |
| Raw mixed-text LLVM lines | 72,861 | 79,703 | 77,011 | 77,266 |
| AOT executable bytes | 577,592 | 619,552 | 594,744 | 607,120 |

Final 44b reduces whole-process instructions **3.236% versus ea685**, removing 60.52% of ea685's excess over main. It retains 95.83% of the rejected scalar prototype's total fnmatch instruction saving, without its ABI change. It remains **2.230% above main**. Raw LLVM falls by 2,437 lines (3.058%) and the executable by 12,432 bytes (2.007%). These observations do not establish a universal speedup.

Exclusive profile costs sum to the Callgrind total; inclusive call-edge rows are not summed again. Inlining moves attribution between functions, so per-symbol differences are not independent causal estimates. The bound Pattern.match adapter still costs nine additional instructions per call over main in this profile; that residual cost is not fixed here.

## Rejected scalar-depth alternative and controls

The prototype passes active logical depth as a private scalar argument through closed direct-call graphs, retaining original public/indirect boundaries. It reached 122 functions in the mixed module. Fourteen hosted tests and twelve focused native executions passed; it did not receive full bootstrap or CI validation and is not a production-ready feature.

Its object-call control increased instructions **7.686%**, consistent with replacing useful bounded-region amortization with per-call scalar checks. Almost all of its fnmatch saving came from the same `charset` shape. The smaller policy change retains the useful object-call region. The rejected patch and all results are preserved separately and are not applied to the source PR.

These controls execute one warm kernel and seven measured kernels per process. Counts include initialization and all eight executions, and therefore differ in scope from isolated-kernel counts in older reports.

| Control | Input n | ea685 instructions | Scalar prototype | Final 44b | Final delta |
|---|---:|---:|---:|---:|---:|
| Ordinary calls | 1,000,000 | 50,247,055 | 50,247,035 | 50,246,967 | -88 |
| Object calls | 10,000 | 134,280,036 | 144,600,991 | 134,280,034 | -2 |
| JSON calls | 1,000 | 251,849,210 | 251,308,756 | 251,849,188 | -22 |

All final-policy differences are below 0.0002% and effectively unchanged at these sizes. A future selective scalar scheme would need to preserve profitable region amortization and show broader gains before reconsideration.

## Actual-driver JIT instruction profiles

The fnmatch profile at `n=1000` warms and verifies an isolated runtime cache for each role, then profiles exactly one actual user `opt` invocation and whole `lli`. Whole `lli` includes machine-code generation, program execution, runtime, GC and teardown; it is not pure startup. The controller uses the hosted driver to reach the real LLVM tools; these two tool counts exclude frontend Python execution. Captured optimized bitcode from fd9 is hash-joined to the actual `opt` output. Instrumented elapsed times are diagnostic.

| JIT measure | Main | ea685 | Final 44b | Final vs ea685 |
|---|---:|---:|---:|---:|
| User `opt` instructions | 1,672,753,913 | 1,845,260,867 | 1,800,303,546 | -2.436% |
| Whole `lli` instructions | 8,335,472,242 | 9,118,611,547 | 8,899,675,882 | -2.401% |
| Combined instructions | 10,008,226,155 | 10,963,872,414 | 10,699,979,428 | **-2.407%** |
| Optimized LLVM lines reaching `lli` | 48,409 | 54,173 | 52,499 | -1,674 |
| Function definitions reaching `lli` | 226 | 270 | 251 | -19 |
| Optimized user bitcode bytes | 673,832 | 738,412 | 721,836 | -16,576 |

The baseline reproduces the earlier approximately 9.55% combined overhead over main. Final 44b reduces it to **6.912%**, leaving a measurable regression. Output, input/wrapper identity, cache reuse and bitcode joins pass. Each role is one instrumented process observation. Raw logs retain two nonfatal Valgrind brk-segment limitation diagnostics per role; all profiled tools returned zero and whole-program output matched pinned CPython.

## Elapsed performance: no AOT win established

The final AOT series uses fnmatch `n=100000`, one warm invocation per role, then all six permutations of main/ea685/final, pinned to CPU 0 with no other team-owned heavy work. References reuse byte-identical binaries from the original measurement phase; hashes are recorded explicitly. They are not claimed as new builds. Every observation is retained, and this series is not pooled with first-policy timings or the previous handoff.

| Final AOT metric, seconds | Main median | ea685 median | Final 44b median |
|---|---:|---:|---:|
| In-program loop | 2.278827 | 2.385464 | 2.448691 |
| Whole-process wall | 2.288784 | 2.392486 | 2.455009 |
| Whole-process CPU | 2.285547 | 2.390375 | 2.453774 |

The final loop median is **2.651% slower than ea685**; the median of paired changes is **0.742% slower**, with the candidate slower in five of six pairs. It is 7.454% slower than main by loop medians. Whole-process wall and CPU point in the same direction. Shared-host variation prevents a confident causal size estimate, but this experiment did not demonstrate an elapsed-time improvement. Lower instruction counts must not be presented as a verified wall-time speedup.

A separate uninstrumented native-driver JIT controller attempted fresh runtime-cache preparation, then reuse and six balanced AB/BA pairs at `n=1000`. **Neither attempt reached the timed pairs.** In the first attempt, baseline cold preparation passed but candidate preparation returned 1 because its temporary directory was not empty at cleanup. In the fresh repeat, both baseline and candidate cold preparation returned 1 at cleanup. Both roles' warm-reuse invocations passed in both attempts, with CPython-matching output. All source/tool identities remained stable.

Both raw attempt records retain `complete: false`, `valid: false` and zero timed observations. Warm-up durations are not promoted to performance samples. Static inspection found real unlink/rmdir calls in the native runtime and identical driver-main raw IR between first-policy and final-policy compilers; it did not establish a cause. The failure is observed on the previous PR as well as the candidate, but an environmental cause or pre-existing compiler bug has not been proven. Native-JIT elapsed comparison is therefore unavailable, and this cold-cache cleanup failure remains an explicit local limitation alongside the performance hold.

Final CI performance smoke independently recomputes all 49 comparisons across 11 workloads and marks each advisory classification `ok`. Its fnmatch changes against main are +12.17% JIT process, +6.20% JIT loop and +1.53% AOT loop; JSON is +8.69%, +6.55% and -1.73%, respectively. The smoke warning threshold (20% together with 5 ms) is not the PR acceptance budget. These samples come from a separate runner/input configuration and are not used to claim improvement over older CI runs or local measurements. The performance hold remains.

## Validation on final 44b

- Local `make check-fast`: 421 passing tests, including 220 typed tests; local IR/runtime probes cover 43 IR programs. These totals overlap CI.
- Final native bootstrap reaches identical compiler and runtime IR fixed points. Its compiler IR has 808,422 lines and runtime IR has 18,805 lines. The ea685 reference in `build/ref` is reused byte-for-byte from the previously fresh baseline build under Make's normal reference cache rule.
- Compiler IR SHA-256 is `ce874ff52970f421fd4f0459bc6c3e21bfea6c212d774ab54cd8c8bf1c4f192b`; runtime IR is `940a694da5ea93214d1308a8eb635b47d8d0a9d4256c63d084c24f5099f8aa5f`. Stage-one, stage-two and published local native compilers match byte-for-byte at `aa1c7c0a0fe38d1e2da4e0a75017020aff0b5add647996e250818dd28c9b2bef`. All 130 consumed source inputs match saved prebuild hashes and pinned Git blobs.
- Six fixtures pass in both native JIT and AOT with `PYSTACHY_JIT_INLINE=0`; the scoped-file fixture also passes JIT with program-only GC stress at every allocation: 13 executions, zero failures, stable inputs. These assertions concern the fixture executions; the existing harness suppresses the return status of its preliminary cache warm-up, so they do not certify cold-cache preparation.
- The unmodified standard `make irsame REF=ea68529b...` retains exit 2 and **297 of 3,920 strict differences**. Expected IR changes do not convert that command into a pass.
- The recorded 3,924-case comparison retains strict exit 1, `status: failed`, and `gate_passed: false`: 299 differences, comprising 238 byte-different LLVM outputs and 61 diagnostic differences. All cases are present, with zero changed exit statuses, missing cases, validation errors or input mutations. A separate assessment proves all 61 diagnostic changes are 106 checkout-path spans in 15 corresponding byte-identical library files; every other message byte is identical. Independent replay verifies all 61 proofs and the 106 exact spans against live files and pinned Git blobs. Its bounded IR audit finds the compiler self-source, index-key fixture and object/ordinary probes byte-identical; representative changed maze/JSON outputs remove selected private bodies, while Monte Carlo differs only in an embedded checkout-path string and length. No anomaly was found in that audited scope; this is not an all-shape semantic proof. This does not relabel changed LLVM as a strict pass; some LLVM differences are embedded diagnostic-path strings, so the 238 count is not a count of optimization-caused changes.
- Final CI: all seven workflows completed on attempt 1; all 61 jobs are accounted for, with 59 successes and exactly two expected skips (same-repository DCO and main-only coverage badge publication). All 31 original verification reports independently remerge with exit 0: 54 logical stages, 84 group-stage records. Original reports are unchanged; the result matches the published aggregate apart from collection timestamp/evidence-root fields. All 37 downloaded artifact archives match provider sizes and SHA-256 hashes, and every ZIP member passes its CRC check. Lint runs all 32 expected unittest commands: 926 tests, zero skips, plus Ruff, actionlint, mypy on 48 compiler files and recording checks. Both formerly failing `index_key` locations pass. CI compiler/runtime IR hashes equal the local fixed points; its native binary has its separate runner-specific identity.

The standard comparison has 3,920 inputs: 2,136 non-rejections and 1,784 expected rejections. The recorded superset explicitly adds four `bench/recursion/*.py` probes, giving 3,924. Removed/added diff lines are not whole-module code-size measurements, and byte-different LLVM is not a semantic-equivalence proof.

### Historical first-policy failure remains visible

First-policy 1ff tested merge `e55d22024299083ca86f551b29cb1550daee3cd3` and tree `5459378ebc5816fb1a410236a75c9a78b61f4d60`. Its 61 jobs ended in 55 successes, three failures and three skips. Hosted coverage and CI/contracts failed on the unchanged `index_key.calls` expectation; the aggregate also failed. One additional coverage-report skip followed that failure. The allocation invariant itself still held, but useful private Grid regions had been removed. The loop-exit refinement fixes that missed optimization without refreshing the expectation.

First-policy local `irsame` had 307/3,920 differences. Its recorded 3,924 comparison retains strict failure with 309 differences: 248 LLVM and 61 diagnostics. Separate byte-span proof identifies 106 checkout-path spans in 15 byte-identical library files, with every other diagnostic byte unchanged. It has no changed exit status, missing case, validation error or input mutation. These historical records remain intact and are not reused as final 44b's results.

## Environment, evidence and remaining limit

Local measurements use CPython 3.13.16, LLVM/Clang 18.1.3 and Valgrind 3.22.0 on Intel Xeon Platinum 8573C. libc was updated before all authoritative local builds and measurements, with no later toolchain change. Roles have separate homes/caches, fixed workload paths and consumed-input manifests. CI uses separate runners and artifacts, so its elapsed samples are not pooled with local results or older CI runs.

The [evidence index](../../bench/recursion/loop-profitability-996/README.md) describes exact controllers, patches, archives, manifests, raw commands/streams, all timing vectors and failed records. Raw research is on a separate branch and must not be merged into the source PR. The previous ea685 handoff remains at `1a6567cbc62a31b53b49c581af72f6846c489167`; its identities and measurements remain historical.

The result supports improving policy in Pystachy's typed-IR optimizer before changing its ABI or dropping compatibility. LLVM determines the cost of resulting code, but a large measured cost came from Pystachy's decision to create a version at all. This does not establish that every remaining cost can be removed at that layer. Existing logical-depth accounting still differs from CPython's internal frame accounting and does not bound arbitrary foreign recursion or excessive physical stack use. No new restriction was added and no replacement numerical performance budget has been accepted.
