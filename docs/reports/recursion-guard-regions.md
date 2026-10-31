# Recursion guard regions: measurements and validation

This report separates final frozen-source measurements from development
experiments. The final candidate contains bounded whole-function versioning,
direct-return partial versioning with bounded child inlining, and the scoped
native-file lifetime proof. The validation section records fresh native and hosted checks. The ordinary/object scaling instruction cost is
removed, and JSON instruction overhead is reduced further. Elapsed-time
acceptance remains open: the full final series reports an object JIT regression
that separate controls do not reproduce consistently. All series are retained;
the controls do not replace the unfavorable full-series result.

## Implementation and scope

This continuation adds **693 net compiler/runtime source lines** over PR #996's
previous `993fb17e` head. The existing leaf-entry checks, terminal-path publication,
regex fallback repair and recursion-state alias metadata remain in place. The new
`recursionregion` pass selects between a proven unchecked path and the complete
guarded body using the non-raising test `needed <= limit - depth`.

Whole-function versioning applies where source calls repeat in a control-flow
cycle. A bottom-up proof computes the maximum simultaneous counted depth across
the complete direct-call graph; recursion cycles and unknown callees fail the
proof. The selector does not raise early. Insufficient headroom executes the
original body, so zero-trip loops and side effects before the failing call retain
their behavior. Only calls inside the private closed graph use unchecked entries;
the original callable symbols and addresses stay guarded.

The final layout correction gives only **maximal selected regions** a separate
`noinline` entry, emitted before the guarded wrapper. Nested private descendants
remain eligible for ordinary inlining, and independent roots can share them.
This is a general graph and emission rule. It addresses the LLVM 18 object-loop
regression found after instruction counts improved: keeping hot and guarded
bodies together, or placing the separate hot entry after its fallback, could
still lose elapsed time. The correction changes placement and inlining policy
without changing the depth proof or moving a failure before source side effects.

A second, narrower form reserves exactly two frames for a root and its immediate
leaf child. The returning path omits their redundant accounting. Before an
observer, the root publishes its active depth and keeps the whole forward suffix
guarded; a child's terminal observer path publishes both omitted frames. The
proof includes hidden check-failure edges and rejects repeated publication or a
return to unchecked work after an observer. Both private layers inline, with
cost charged at each rewritten child callsite. Whole-function and partial
selection use separate budgets of 8,192 operations/slots overall and 2,048 per
region, measured on input IR rather than final LLVM. Whole-function depth is
capped at 64, and partial roots start at no more than 768 operations/slots.

Callbacks, limit changes, generators and local exception handlers remain
conservative boundaries. Hidden numeric identity arguments/results are copied
unchanged. Tuple-return roots remain unversioned when a forwarding return would
defeat aggregate-return optimization; private descendants remain eligible.

The file restriction is narrowed only when **every native open is immediately
protected by the existing unwind action for that exact result**, outside a
generator or coroutine. These arguments are already explicit GC roots until
deterministic close. One unmanaged open, weakref registration, exit hook, or
CPython embedding/extension boundary still disables both optimizations for the
program. This does not change collector policy or establish deterministic
destruction for arbitrary objects. Existing file-finalization outputs remain
unchanged.

Use `PYSTACHY_OPT=-recursionregion` to disable the new versioning while retaining
leaf elision, or `PYSTACHY_OPT=-recursionleaf,-recursionregion` to retain full
original bookkeeping on the same compiler. `PYSTACHY_JIT_INLINE=0` still inlines
the mandatory private partial versions and recursion-accounting helpers.

## Source identity and preparation

The comparison includes all three requested implementation stages and the prior
optimized head, so gains from this continuation can be distinguished from gains
already present at `993fb17e`.

| Label | Meaning | Published identity or frozen local commit | Exact tree |
|---|---|---|---|
| Main | Post-#997 baseline without recursion guards | Published `06e3ad5d08514ba31fb231fe4636a962fe6578e3` | `db120afecf27ff03b08c25624dc64be8b06bac3b` |
| Original | Original guards, integrated with #997 and the regex repair | Published `0166fbb556754b3d23ac68647baf458a55bd74cb` | `c2c4ffe9efdb1c9dfe9511e320cedc78ff675fac` |
| Prior | The previous optimized PR head | Published `993fb17eed953f332661841f7793a30902738242` | `2eb5436ed29787064531da78679ba27067317e89` |
| Candidate | This continuation after the measured layout correction | Remote source commit `72712b21813adf721aaa4e99f1f85b9eff8eb149` | `c597da7cd7a2ee1fddd1bf7dbd61e3c233ac0357` |

The first three local clones use different commit metadata but the listed exact
trees. Their local commits are `4ef9cb7b1872445596ea5df01f0dfed365faf875`,
`d5bc7a93504e9e0ed0d8bb125d3a39a8711911cb`, and
`a7c38c516e9730f4da8eeff4456c495e1ab29e0e`, respectively.
The candidate was measured at local `37913cf96eabe1ef7446f56dc64e4d1f01b7282b`;
the remote source commit has exactly the same tree. Later documentation/results
commits do not relabel this frozen source snapshot.
The full local verification snapshot is local `480b5554c44a8a73d463999a69e41d106727f48b`,
published as immutable `2fe3aa788c0d667fb89700fe13b5a5cb24172a68`, tree
`d19e1b496ecbca3530bb45f409ee7da2d9b94375`. Its only differences from the measured
source tree are documentation and four call-list snapshots with seven moved,
otherwise unchanged rows. All 131 consumed source inputs match.

All 131 consumed compiler, runtime, library, MPZ, Ryu, and build inputs have
SHA256 manifests, including importable untracked source. The candidate manifest
matched the root checkout both before and after cloning. Every measurement
phase checks source and probe manifests before and after execution; all
executables and raw LLVM modules are individually hashed. Each variant has a
separate runtime cache and the normal driver invalidation remains active.

Final preparation completed on 2026-10-31 at 04:32:38 UTC: six cases across four
variants passed all 48 native JIT/AOT checksum checks against CPython. There are
five unique probe source files: warmed short and warmed long use the same file
and byte-identical emitted modules/executables, with different iteration
arguments. Every
printed kernel result, including the normal warmup and all seven subsequent samples, is
validated. The four additional calls in the warmed wrapper discard their results;
they are setup calls. The final JSON candidate raw LLVM has SHA256
`80d135b599ad31d3f6ecdc0e53fbdc91f1e5f09d1035f7ccc2a48021ccc40ec4`.
The corrected candidate uses an entirely fresh measurement series. The rejected
earlier layout and its measurements remain separately recorded below.

## Measurement method

The toolchain is CPython 3.13.16, LLVM/Clang 18.1.3 and Callgrind 3.22.0 on an AMD
EPYC 9V74 Linux host. Native measurement processes are pinned to CPU 0. Hardware
instruction counting through `perf_event_open` is unavailable in this
environment (the userspace retired-instruction request returns `ENOENT`), so
instruction comparisons use Callgrind. Compilation, profiling and elapsed
measurement phases are serialized, and the other local validation jobs pause
during the performance lane. The underlying host remains shared.
The CPython-hosted compiler emits the measured native JIT/AOT programs; compile
costs below measure that compiler invocation, not the self-hosted frontend.
The rebuilt native compiler also emitted all six candidate raw LLVM modules
byte-for-byte identically, using the matching 131-input compiler home. Native
and hosted frontend parity therefore covers the code measured here.

Eight process rounds rotate all four variants. The first four rounds use forward
rotations; the next four reverse the complete rotations. An explicit assertion
confirms that every variant occupies every order position exactly twice. Each
process contains one normal untimed warmup and seven measured kernel calls.
Reported times are medians of the eight process medians, with the observed
process-median ranges retained. The full report also records paired ratios
within each round. Kernel timers exclude compilation, process startup, printing
and, for the file case, file I/O.

The earlier three-variant every-other-round reversal was unbalanced for four
variants. It was corrected before the first four-way elapsed series, with that
rejected series retaining the before/after harness hashes and intended orders.
The corrected candidate uses the balanced rule from its preparation phase
onward. Per-phase harness identities are retained; no source, probe or executable
was changed or relabelled by the scheduling correction.

| Case | Work per measured call | Untimed kernel calls before samples | Purpose |
|---|---:|---:|---|
| Ordinary calls | 10,000,000 scalar calls | 1 | Isolate retained entry-check cost |
| Object calls | 100,000 iterations, 64 updates each | 1 | Repeated bounded method calls |
| Original short JSON | 2,000 parses of the original 32-key input | 1 | Preserve the historical short experiment |
| Warmed short JSON | 2,000 parses of the same input | 5 | Separate process warmup from input length |
| Warmed long JSON | 20,000 parses of the same input | 5 | Longer steady-state kernel |
| Scoped-file JSON | 20,000 parses of the same input | 1 | Exercise recovered eligibility with native file creation |

The committed scoped-file probe writes and reads its JSON through two explicit
native `with open(...)` scopes, then closes both before timing. It accepts an
explicit scratch filename. Its timed kernel is the same JSON parser workload;
this measures optimization eligibility in a program that opens native files,
not storage throughput. Weakrefs and unmanaged native-file lifetimes remain
conservative exclusions.

Instruction counts use 100,000 ordinary calls, 5,000 object iterations, or 2,000
JSON parses per kernel, with eight kernel calls including warmup. They include
native runtime and GC work while excluding startup, the compiler, timers and
printing. JSON and object AOT use the exact unmodified timed executable with
Callgrind collection toggled at `f.kernel` entry/return; eight dumps are required.
If the original `f.kernel` envelope has been inlined, as in the ordinary AOT
control, collection instead uses explicit markers around its complete source
invocation; private fast callees can still remain. Actual ORC JIT uses the same
marker approach. For every instrumented
input, all pre-existing raw LLVM function bodies other than the top-level
initializer must remain byte-identical. Marker counts include their small
constant overhead. These are instrumented equivalents: raw body equality does
not prove identical machine code after LLVM sees changed top-level call sites,
especially when the original ordinary AOT envelope has been inlined. Exact AOT binary
counts for JSON and object have the stronger identity guarantee. These are
dynamic instruction counts, not hardware cycle or cache-miss measurements.

The first final count attempt stopped after seven successful records because
the harness's word-boundary symbol regex mistook `rf.f.kernel` for the original
`f.kernel`. The ordinary candidate AOT binary has only the private fast symbol,
so collection at the absent original entry produced zero dumps. This was a
harness failure, not zero-cost execution. The correction matches the exact last
symbol token, checks all 48 prepared artifact hashes, and repeats all 32 counts
under one corrected harness identity. The failed phase, seven preliminary
records, zero-dump profile, and hashes remain archived. That failed run's process
output was checksum-validated in memory but not persisted before the assertion;
the corrected harness persists each attempt before asserting its collection
scope.

The object candidate AOT wrapper tail-transfers into its private fast kernel.
All eight profiles were independently checked: every positive instruction cost
lies in the wrapper's descendant graph, each dump contains one fast-kernel
transfer, and the final profile has zero collected work. The aggregate includes all 152 wrapper instructions and the fast kernel
with its runtime callees, totaling 67,032,776. Timer, print and marker functions
have zero collected instructions in that profile.

Compile-cost sampling uses four rotated samples for six case labels, four
variants and two stages: 192 observations across five unique source files.
Warmed short and warmed long provide two labelled sample sets for the same
compilation input. IR emission includes compiler
frontend work; AOT build includes the LLVM/linking stages with a warmed runtime
cache. Every rebuilt module and executable must match the preparation artifact
SHA256. The range and median are descriptive: four shared-host observations do
not establish precise compilation-speed changes.

## Final results

All measurement phases completed: 32 instruction counts, 384 elapsed processes
containing 2,688 measured kernel calls, and 192 compile observations. All sources,
probes and prepared outputs remained unchanged. Completing a measurement phase
does not mean its elapsed-performance acceptance passed.

<!-- FINAL_RESULTS_START -->
### Dynamic instructions

| Kernel / mode | Main | Original guards | Prior head | Candidate |
| --- | --- | --- | --- | --- |
| Ordinary JIT | 8,000,160 | 10,400,217 | 10,400,217 | 8,000,233 |
| Ordinary AOT | 5,000,217 | 5,000,289 | 5,000,289 | 5,000,296 |
| Object JIT | 90,036,184 | 115,639,360 | 97,717,792 | 90,036,392 |
| Object AOT | 67,032,624 | 82,394,752 | 72,194,240 | 67,032,776 |
| JSON, original short JIT | 572,271,057 | 622,599,568 | 608,558,798 | 599,385,724 |
| JSON, original short AOT | 526,398,962 | 568,691,726 | 545,551,029 | 536,695,516 |
| JSON, scoped file JIT | 571,044,526 | 621,574,448 | 620,573,015 | 598,367,827 |
| JSON, scoped file AOT | 525,479,955 | 567,696,774 | 557,072,830 | 535,776,535 |

| Kernel / mode | Original vs main | Prior vs main | Candidate vs main | Candidate vs prior |
| --- | --- | --- | --- | --- |
| Ordinary JIT | +30.00% | +30.00% | +0.00% | -23.08% |
| Ordinary AOT | +0.00% | +0.00% | +0.00% | +0.00% |
| Object JIT | +28.44% | +8.53% | +0.00% | -7.86% |
| Object AOT | +22.92% | +7.70% | +0.00% | -7.15% |
| JSON, original short JIT | +8.79% | +6.34% | +4.74% | -1.51% |
| JSON, original short AOT | +8.03% | +3.64% | +1.96% | -1.62% |
| JSON, scoped file JIT | +8.85% | +8.67% | +4.78% | -3.58% |
| JSON, scoped file AOT | +8.03% | +6.01% | +1.96% | -3.82% |

The ordinary/object candidate differences are constant setup work in these kernels.
Across eight counted calls, ordinary JIT/AOT add 73/79 instructions and object
JIT/AOT add 208/152. Their rounded 0.00% entries do not claim identical execution.
JSON retains measurable instruction overhead.

### Elapsed kernel times

| Kernel / mode | Main ms | Original vs main | Prior vs main | Candidate vs main | Candidate vs prior |
| --- | --- | --- | --- | --- | --- |
| Ordinary JIT | 11.498 | -0.45% | +0.96% | -0.63% | -1.57% |
| Ordinary AOT | 9.297 | -0.08% | -0.04% | +0.61% | +0.65% |
| Object JIT | 13.150 | +7.75% | +0.18% | +10.22% | +10.03% |
| Object AOT | 11.189 | +9.61% | -0.73% | -0.92% | -0.19% |
| JSON, original short JIT | 5.384 | +14.15% | +6.62% | +2.28% | -4.07% |
| JSON, original short AOT | 5.040 | +10.46% | +5.15% | -0.19% | -5.07% |
| JSON, warmed short JIT | 5.335 | +7.16% | +2.46% | +4.62% | +2.11% |
| JSON, warmed short AOT | 4.909 | +4.70% | -0.16% | +3.64% | +3.80% |
| JSON, warmed long JIT | 52.486 | +13.60% | +0.33% | +2.70% | +2.37% |
| JSON, warmed long AOT | 48.703 | +5.36% | +2.07% | -0.87% | -2.89% |
| JSON, scoped file JIT | 52.071 | +11.13% | +9.38% | +1.52% | -7.18% |
| JSON, scoped file AOT | 48.021 | +6.25% | +5.91% | +1.85% | -3.83% |

Observed process medians in milliseconds, formatted median [minimum, maximum]:

| Kernel / mode | Main | Original guards | Prior head | Candidate |
| --- | --- | --- | --- | --- |
| Ordinary JIT | 11.498 [11.185, 12.496] | 11.446 [11.066, 13.325] | 11.607 [11.134, 12.189] | 11.425 [11.189, 11.774] |
| Ordinary AOT | 9.297 [9.112, 9.747] | 9.289 [9.150, 10.481] | 9.293 [9.067, 10.007] | 9.354 [9.007, 9.882] |
| Object JIT | 13.150 [12.610, 19.786] | 14.169 [13.684, 16.177] | 13.173 [12.636, 15.499] | 14.494 [13.149, 16.220] |
| Object AOT | 11.189 [10.689, 16.053] | 12.264 [11.814, 13.880] | 11.107 [10.685, 12.032] | 11.086 [10.591, 15.910] |
| JSON, original short JIT | 5.384 [5.033, 6.716] | 6.145 [5.886, 8.342] | 5.740 [5.216, 7.938] | 5.506 [5.068, 6.032] |
| JSON, original short AOT | 5.040 [4.470, 7.174] | 5.567 [4.924, 7.825] | 5.300 [4.886, 7.543] | 5.031 [4.855, 7.449] |
| JSON, warmed short JIT | 5.335 [5.085, 7.949] | 5.717 [5.544, 8.347] | 5.466 [5.126, 6.291] | 5.581 [5.092, 8.777] |
| JSON, warmed short AOT | 4.909 [4.534, 5.114] | 5.139 [4.939, 7.723] | 4.901 [4.586, 7.357] | 5.087 [4.701, 5.597] |
| JSON, warmed long JIT | 52.486 [51.068, 55.790] | 59.624 [57.109, 63.417] | 52.657 [51.903, 57.252] | 53.905 [51.745, 60.752] |
| JSON, warmed long AOT | 48.703 [45.680, 50.351] | 51.316 [48.447, 55.405] | 49.713 [47.517, 51.774] | 48.279 [47.145, 52.433] |
| JSON, scoped file JIT | 52.071 [50.711, 64.190] | 57.866 [55.679, 59.166] | 56.955 [54.024, 58.282] | 52.864 [51.488, 66.395] |
| JSON, scoped file AOT | 48.021 [46.264, 50.487] | 51.023 [48.321, 54.969] | 50.857 [49.274, 59.691] | 48.910 [47.208, 51.483] |

Within-round ratios to main, median [minimum, maximum] across the eight rounds:

| Kernel / mode | Original guards | Prior head | Candidate |
| --- | --- | --- | --- |
| Ordinary JIT | +0.01% [-9.35%, +11.01%] | +0.02% [-7.15%, +6.78%] | +0.07% [-6.94%, +3.14%] |
| Ordinary AOT | +0.24% [-1.95%, +7.53%] | +0.99% [-2.84%, +3.60%] | +0.99% [-3.76%, +3.79%] |
| Object JIT | +4.27% [-25.73%, +26.21%] | +3.08% [-36.14%, +16.72%] | +9.95% [-32.72%, +26.55%] |
| Object AOT | +10.36% [-16.19%, +21.12%] | -0.89% [-26.75%, +6.67%] | -0.65% [-1.56%, +11.27%] |
| JSON, original short JIT | +11.94% [-12.36%, +65.73%] | +5.20% [-21.35%, +49.57%] | -0.43% [-11.97%, +19.84%] |
| JSON, original short AOT | +11.25% [+4.08%, +16.37%] | +6.60% [-24.56%, +45.52%] | +5.03% [-3.06%, +43.10%] |
| JSON, warmed short JIT | +5.64% [-5.69%, +12.55%] | -1.97% [-30.25%, +21.39%] | +1.15% [-9.31%, +12.10%] |
| JSON, warmed short AOT | +3.65% [+0.96%, +64.85%] | +0.18% [-7.25%, +57.03%] | +3.49% [-2.95%, +9.45%] |
| JSON, warmed long JIT | +12.28% [+6.26%, +18.19%] | +1.20% [-6.97%, +10.99%] | +0.82% [-2.44%, +16.86%] |
| JSON, warmed long AOT | +6.12% [+1.56%, +12.73%] | +2.79% [-2.79%, +11.73%] | +2.26% [-5.71%, +8.47%] |
| JSON, scoped file JIT | +11.13% [-11.49%, +14.27%] | +8.52% [-15.84%, +12.36%] | +1.63% [-18.42%, +28.24%] |
| JSON, scoped file AOT | +6.71% [+4.23%, +13.32%] | +6.08% [-0.47%, +25.58%] | +2.91% [-0.30%, +4.63%] |

### Compilation and emitted size

Compilation seconds, median [minimum, maximum] of four rotated samples.
The table shows four principal program shapes; all six case labels remain in the raw record.
There are five unique source files; the two warmed labels share the same compilation input.

| Program / stage | Main | Original guards | Prior head | Candidate |
| --- | --- | --- | --- | --- |
| Ordinary ir | 0.048 [0.046, 0.058] | 0.049 [0.044, 0.061] | 0.046 [0.044, 0.054] | 0.050 [0.046, 0.065] |
| Ordinary build | 0.325 [0.314, 0.377] | 0.366 [0.338, 0.372] | 0.349 [0.314, 0.355] | 0.384 [0.346, 0.422] |
| Object ir | 0.056 [0.050, 0.070] | 0.048 [0.047, 0.051] | 0.050 [0.048, 0.063] | 0.052 [0.050, 0.057] |
| Object build | 0.350 [0.342, 0.397] | 0.357 [0.339, 0.405] | 0.359 [0.340, 0.370] | 0.361 [0.353, 0.391] |
| JSON, original short ir | 0.144 [0.140, 0.175] | 0.145 [0.138, 0.151] | 0.153 [0.141, 0.158] | 0.161 [0.152, 0.176] |
| JSON, original short build | 1.740 [1.596, 2.025] | 1.698 [1.611, 1.777] | 1.785 [1.749, 1.810] | 1.843 [1.789, 1.954] |
| JSON, scoped file ir | 0.142 [0.138, 0.147] | 0.140 [0.138, 0.143] | 0.143 [0.139, 0.149] | 0.162 [0.156, 0.179] |
| JSON, scoped file build | 1.772 [1.723, 1.884] | 1.768 [1.710, 1.840] | 1.876 [1.709, 1.949] | 1.869 [1.836, 1.935] |

Emitted size: raw LLVM lines / AOT executable bytes.

| Program | Main | Original guards | Prior head | Candidate |
| --- | --- | --- | --- | --- |
| Ordinary | 194 / 46,312 | 228 / 46,424 | 246 / 46,424 | 317 / 46,464 |
| Object | 300 / 46,528 | 337 / 46,640 | 352 / 46,640 | 519 / 46,664 |
| JSON, original short | 4,154 / 153,688 | 4,275 / 153,856 | 4,289 / 153,808 | 5,651 / 158,072 |
| JSON, scoped file | 4,191 / 167,608 | 4,312 / 171,864 | 4,317 / 171,864 | 5,688 / 176,080 |

Raw module line counts include retained guarded fallbacks and private clones.
Executable bytes include the runtime and alignment, so size growth is not equivalent
to instruction-cache traffic. Compile medians have four samples and are descriptive.

<!-- FINAL_RESULTS_END -->

The original short JSON AOT aggregate median is 0.19% below main in this series,
while the median within-round ratio is +5.03% and the paired range spans −3.06%
to +43.10%. The warmed-short aggregate is +3.64%, and the warmed-long aggregate
is −0.87%. These disagreeing summaries and wide process ranges keep the short
AOT uncertainty open. The longer and warmed experiments are separately labelled
evidence; they do not replace the historical-size case or establish a precise
speedup. The file-program instruction result is clearer: candidate JSON overhead
is +4.78% JIT and +1.96% AOT, down from the prior head's +8.67% and +6.01%.

The expanded versions also have a compilation and code-size cost. For example,
JSON AOT-build medians are 1.740/1.698/1.785/1.843 seconds for
main/original/prior/candidate, and ordinary build medians are
0.325/0.366/0.349/0.384 seconds. The four-sample ranges above limit precision.
Original-short JSON grows from 4,154 to 5,651 raw LLVM lines and from 153,688 to
158,072 executable bytes compared with main; private fast bodies and retained
guarded fallbacks account for deliberate IR expansion.

## Why these transformations were selected

### A rejected layout exposed an elapsed-time regression

The first complete four-way series used local `b04e6b44`, published as immutable
source commit `8af0ea7c`, tree `a29c339abbbc92516fa0aa0eec78539b11bccdb0`.
It removed repeated ordinary/object instruction overhead, but its object JIT
median was **11.73% slower than main**. It was slower than the prior head in all
eight paired rounds. That candidate was rejected before compile-cost sampling;
all 32 counts and 384 timing processes remain in the rejected-results JSON.

Actual ORC object capture showed that LLVM had inlined the fast and guarded
bodies into one function. Moving common error blocks beyond the guarded body
widened three hot conditional branches from two bytes to six. The hot loop grew
from 52 to 62 encoded bytes despite executing no more instructions. Those facts
identified a layout concern; they did not establish a hardware cause.

The follow-up controls were deliberately separate from the complete series:

| Object JIT development control | Main median | Control median | Result |
|---|---:|---:|---|
| B04 layout reproduced | 12.933 ms | 14.739 ms | Regression reproduced |
| Prefer the fast selector edge | 12.933 ms | 14.183 ms | Insufficient |
| Keep the fast root separate, in its old position | 12.933 ms | 14.585 ms | Insufficient despite baseline-like function body |
| Align that separate root to 64 bytes | 13.430 ms | 14.033 ms | Partial, noisy improvement |
| Mark the root call as a tail call | 13.430 ms | 14.555 ms | Insufficient |
| Emit the separate fast root before its guarded wrapper | 13.430 ms | 13.049 ms | Back within the baseline range |

Each comparison belongs to its labelled ten-round five-way series; rows from
different series are not pooled. A direct-`lli` 2×2 diagnostic crossed the prior
and B04 optimized modules with the prior and B04 runtime libraries. The slowdown
followed the module with either runtime, so the newly exported room helper was
not its primary cause in this workload. Runtime `pys_mod` also had the same
instructions and symbol offset in all three prepared runtime libraries.

The source correction marks only maximal bounded entries `noinline` and emits
each before its guarded wrapper. Nested roots and shared leaf versions remain
inlineable. It retains the existing private symbols and changes emission order,
without benchmark-name conditions or ABI changes. A separate eight-round
generic-source control measured main/prior/B04/corrected object JIT at
13.275/13.316/14.691/13.034 ms; AOT was
11.218/10.910/10.974/10.979 ms. Small differences within that spread are not a
speedup claim. The corrected ORC fast function has the same 222 unrelocated
machine-code bytes and text offset zero as main's kernel, including registers
and short branches. This is a function-body identity check, not whole-binary
identity. The final table above comes from the subsequent fresh full series.

`recursion-region-rejected-b04.json` and
`recursion-region-layout-controls.json` preserve the rejected result and all
follow-up samples, identities, transforms, and object hashes. They show why
removing instructions alone was insufficient to accept the optimization.

### The final object elapsed result remains unresolved

The fresh full series measured corrected object JIT at **14.494 ms versus
13.150 ms for main: +10.22%**. The prior head measured 13.173 ms. Candidate
process medians ranged from 13.149 to 16.220 ms; main ranged from 12.610 to
19.786 ms. The paired candidate/main median was +9.95%, with a range from
−32.72% to +26.55%. Candidate was slower than prior in seven of eight rounds.
Object AOT was −0.92% relative to main in the same full series. The unfavorable
JIT result remains in the final table and limits performance acceptance.

The preceding generic-source control used a transparent `lli` wrapper for
diagnostic capture, so its captured object alone could not establish actual
timed relocation or placement. A subsequent read-only capture inspected an
owned normal-driver child through `/proc`, without wrapping `lli` or changing
the benchmark, LLVM path, cache settings, or source. Its optimized module was
identical to the control except for the temporary source filename and module
label. The main kernel and candidate fast kernel were both at page offset zero,
and **all 222 relocated function bytes were identical**, including the direct
call displacement to `pys_mod`. That runtime function also had identical code
and symbol offset. The runtime cache payloads and AOT binaries matched the
generic-source control. This rules out the previously observed widened-branch
layout difference in these captures; it does not prove identical hardware
execution conditions across processes.

One separate, balanced 32-process object JIT control then kept the exact normal
driver and full-series paths/settings while an external observer on CPU 8 read
the measured CPU-0 child's scheduler counters. It measured main/original/prior/
candidate at 14.083/14.849/13.393/13.911 ms. Candidate was −1.23% relative to
main and +3.87% relative to prior. Paired candidate/main ratios ranged from −9.54%
to +49.10%, with three of eight rounds slower. Whole-`lli` runqueue waiting was
below 0.12 ms per process; those counters include LLVM startup and warmup and
cannot locate each kernel interval. Ordinary in-guest queue delay therefore
does not explain the observed spread. CPU-frequency, shared-resource and host
effects were not measured. The control demonstrates instability, without
establishing a cause or proving that the full-series regression is harmless.

The final source remains a performance candidate. Further acceptance should use
a quieter, controlled performance runner with hardware cycle and cache counters
available. The final-layout diagnostic records preserve all 32 control
processes, whole-process scheduler samples, source/artifact hashes and the
relocated-code comparison separately from the full-series data.

### Guard-cost attribution and JSON profitability

Assembly and Callgrind exposed the remaining ordinary JIT cost directly: the
prior kernel executes three extra loop instructions (depth load, limit compare,
overflow branch), 13 rather than 10 instructions per iteration. The bounded
selector moves that decision outside the repeated region while keeping the
original fully guarded path as the fallback. The initial bounded prototype
removed the ordinary/object scaling cost but regressed JSON. That rejected
result is preserved.

For JSON, selecting the scalar `decoded` wrapper added an out-of-line call and
an unamortized selector. Its AOT self cost grew from 14,336,000 instructions to
20,992,000 across the eight counted kernels. Forcing every whole-function fast
clone inline removed most of the extra call cost but still added 528,000 source
instructions. Requiring a counted call inside a CFG cycle for whole-function
roots avoids that scalar-wrapper regression.

The partial prototype initially selected `value`, `key` and `string`. The
key/string prefixes commonly published depth before returning through guarded
callees, so their selector cost did not pay back. Separate attribution
experiments isolated that loss. The implemented candidate's generic direct-child-return proof
retains `value` to `number` and excludes those key/string shapes without any
JSON-name filtering. LLVM 18 inline remarks showed that cloning also removes
the single-use inliner bonus for some children. Mandatory inlining is therefore
restricted to bounded partial children; the compiler charges each rewritten
call site's child slots and operations against per-root and program-wide
expansion caps. Whole-function clones are not globally forced inline.

The exploration record includes all nine variants, raw IR, assembly, LLVM inline
remarks and instruction profiles. The first partial implementation increased
JSON JIT instructions by 0.217% relative to the prior head despite reducing AOT
instructions. That result was rejected. The selected direct-return and bounded
child-inline experiment reduced both modes (1.509% JIT and 1.623% AOT versus the
prior head). Those figures are development evidence; the final table above uses
fresh frozen-source counts.

The final JSON AOT profiles retain 10,296,554 more instructions than main, or
1.96%. Grouping noninclusive function costs avoids mistaking moved/inlined code
for entirely new work:

| Collected path group | Main instructions | Candidate instructions | Difference |
|---|---:|---:|---:|
| Value/object/number paths and boxing | 224,816,369 | 230,552,449 | +5,736,080 |
| Decoded key path | 10,240,000 | 14,336,000 | +4,096,000 |
| Kernel, parse entry and parser constructor | 1,808,511 | 2,272,591 | +464,080 |
| All other collected work, including runtime/library/GC | 289,534,082 | 289,534,476 | +394 |

These groups mix recursion accounting with LLVM code-generation choices. In
particular, boxing moved out of line, so labeling every runtime-function delta
as GC or every source-function delta as guard cost would be incorrect.

The proof deliberately stops at the recursive object/array/value call cycle.
It does not infer a maximum call depth from the parser's explicit JSON nesting
limit. The numeric direct-return path can use its prechecked child, while the
string/container/error paths publish logical depth and retain guarded callees.
The decoded-key leaf still checks entry depth; key/string scan prefixes usually
continue through other source calls and did not satisfy the profitable
direct-child-return shape. Their earlier broader partial version was measured
and rejected. This leaves repeated decoded-key checks and counted parser entry
paths as concrete remaining sources of cost, along with the changed inlining
and boxing choices identified in the grouped profiles.

The historical short JSON anomaly also warranted a separate measurement
design. Existing roughly 5 ms samples showed slower initial measured calls
across all variants, even though Callgrind work increased as allocation-only
calls progressed into steady-state GC. That supports investigating warmup and
host effects but does not prove a single cause. The final experiment preserves
the original short case, adds a separately labelled warmed short case, and adds
a longer warmed case. It retains every sample and reports their spread rather
than discarding inconvenient initial calls.

## Corrected-layout validation

Fresh local checks use tree `d19e1b496ecbca3530bb45f409ee7da2d9b94375`, published as `2fe3aa788c0d667fb89700fe13b5a5cb24172a68` (local commit `480b5554c44a8a73d463999a69e41d106727f48b`). All **131** measured source inputs match the benchmark revision `72712b21` (local `37913cf9`). Completed phases have identical before/after source manifests and use CPython **3.13.16**, LLVM **18.1.3**, and the compiler's IR verifier. These results replace earlier layout results for the checks below.

| Check | Corrected-layout result |
|---|---|
| Compiler and subset-runtime fixed points | Stages 1/2/3 identical: **803,142** compiler and **18,805** runtime IR lines |
| Typed-IR tests | **191/191** |
| Function-summary tests | **7/7** |
| Compiler-state and ownership tests | **107/107** |
| 19 native fixtures, JIT and AOT | **38/38** |
| Same fixtures, program GC stress | **38/38** |
| Same fixtures, all optimizations disabled | **38/38** |
| Same fixtures, ordinary JIT inlining disabled | **19/19** |
| Four new fixtures, leaf elision disabled, JIT and AOT | **8/8** |
| Native IR and LLVM contracts | **43/43** |
| Runtime signatures, typing and hygiene | **599** runtime entries, **70** exception classes, **172** subset functions; **48** typed source files; Ruff and **11** repository tests passed |
| Native versus hosted benchmark IR | **6/6** raw modules byte-identical, without normalization |
| Full compilation comparison against main | **3,917/3,917** accounted for; no changed status or new rejection |

The native cases cover low-limit leaves, bounded and zero-trip fallback paths, side effects before failure, callback limit changes, exception recovery/rendering, generators, regex fallback, promoted numeric identity, aggregate returns, weakrefs and file closure. The calibrated partial-depth case checks both sides of the two-frame publication boundary, tail-observer depth and hidden division-error precedence. Earlier mutation controls remain separate design evidence; they are not relabeled as a new native run.

The comparison accepted **2,133** and rejected **1,784** cases on both compilers. It preserves intentional LLVM changes and the raw harness's expected exit status **1**; it establishes compilation parity, not runtime equivalence. All **61** changed diagnostics reconstruct byte-for-byte using only verified identical-library filenames: **61** header and **45** nested-call locations across **15** files. The strict header-only audit initially returned **2** with **29** cases requiring the separate supplemental review. Those records and the raw messages remain preserved; no line, column or error text was normalized. The prior main compiler and its complete **8,124-file** source manifest also match the baseline used here.

The rebuilt native compiler SHA256 is `48d0c7fd5b17765c84657fbd1e98adbb057b6dde9069bfd3b99a146066392cab`. Bootstrap took **220.615 seconds** in this run; that single duration is not a compilation-speed comparison.

This is focused local validation plus the full compilation comparison. It does not claim a complete local `make verify` run. The applicable CI matrix must be checked on the final PR head; PR #996 remains draft.

## Reproduction and evidence

Use the four exact source snapshots above, CPython 3.13.16 and LLVM 18.1.3.
Use the candidate's committed `bench/recursion` probes for every variant. Clear
inherited `PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME` settings first, then set
the LLVM path and a separate cache for the selected variant. These portable
commands illustrate one variant; replace the example absolute paths:

```sh
export PYSTACHY_LLVM=/absolute/llvm18/bin
export PYSTACHY_CACHE=/absolute/results/main-cache
PROBES=/absolute/candidate/bench/recursion
RESULTS=/absolute/results/main
mkdir -p "$RESULTS"
cd /absolute/main

python3.13 "$PROBES/json_calls.py" 2000
taskset -c 0 python3.13 -m pystachy ir "$PROBES/json_calls.py" -o "$RESULTS/json.ll"
taskset -c 0 python3.13 -m pystachy build "$PROBES/json_calls.py" -o "$RESULTS/json"
taskset -c 0 python3.13 -m pystachy run "$PROBES/json_calls.py" 2000
taskset -c 0 "$RESULTS/json" 2000
```

Repeat for each program and its tabled iteration count, using distinct output
filenames and per-variant caches. `json_file_calls.py` additionally takes an
explicit scratch filename after the iteration count. Check every result against
CPython before accepting a timing. All variants use default compiler options.

Generate the exact warmed JSON wrapper outside the source checkout:

```sh
python3.13 - "$PROBES/json_calls.py" "$RESULTS/json_warmed.py" <<'PY'
import hashlib
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text()
needle = 'print("warm", kernel(text, n))'
assert source.count(needle) == 1
source = source.replace(needle, 'for warmup in range(4):\n    kernel(text, n)\n' + needle)
data = source.encode()
assert hashlib.sha256(data).hexdigest() == "7a8a94314179ba0797632f7241cb9c6541d891c79ded006b444c8bfd9dfea6cf"
Path(sys.argv[2]).write_bytes(data)
PY
```

Build that wrapper once per variant and run it separately with 2,000 and 20,000
iterations. Its four extra calls precede the normal warmup. The historical report
used three extra warmups; this continuation explicitly uses four and records a
different probe hash. No old warmed measurement is relabelled.

Use these position-balanced orders for both native modes:

```python
names = ["main", "original", "prior", "candidate"]
orders = []
for round_index in range(8):
    offset = round_index % len(names)
    order = names[offset:] + names[:offset]
    if (round_index // len(names)) % 2:
        order.reverse()
    orders.append(order)
assert all(sum(order[position] == name for order in orders) == 2
           for name in names for position in range(4))
```

For each case and round, run all four JIT processes in that order, then all four
AOT processes in that order. Take the median of each process's seven printed
times, then the median of those eight process medians. Keep all sample values
and checksum outputs. Run compile and instruction phases separately from
elapsed timings and other CPU-heavy validation.

For JSON/object AOT counts, use the exact timing binary at the smaller count
iteration size, as in the preceding report's Callgrind recipe:

```sh
taskset -c 0 valgrind --tool=callgrind --error-exitcode=99 \
  --collect-atstart=no --toggle-collect=f.kernel --dump-after=f.kernel \
  --callgrind-out-file="$RESULTS/json.callgrind" "$RESULTS/json" 2000
```

Require eight kernel-return dumps and sum their `summary:` counts plus the final
profile. A missing kernel symbol is an error, never a zero-cost result. For JIT
and ordinary AOT whose original `f.kernel` envelope is absent, use the [previous report's](recursion-guard-optimization.md#reproduction) `ffi.extern`
Callgrind marker recipe and the all-function-body equivalence check described
above. Compile the toggle helper with the same LLVM and run the actual ORC `lli`
process under Callgrind with collection initially disabled.

For compilation, take four samples in forward rotated variant order. Time IR
emission and AOT build separately with a warmed runtime cache, retaining wall
times and requiring every output SHA256 to equal the preparation artifact. Keep
the short/warmed/long wrappers separately labelled even when their emitted
executables are identical.

The curated JSON accompanies this report with exact source/artifact hashes,
dynamic counts, every elapsed sample, all compile-cost samples, tool versions
and balanced orders. The local investigation retains commands, Callgrind dumps, rejected development
candidates, LLVM attribution experiments and captured output, with the failed
first counting attempt's missing process output explicitly noted above.
Exploratory series remain distinct from final acceptance evidence.


Committed evidence:

- [Final measurements](../../bench/recursion/results/recursion-region-results.json): four source manifests, all counts, elapsed samples and compile observations.
- [Rejected first layout](../../bench/recursion/results/recursion-region-rejected-b04.json): the complete earlier series, retained with its rejection reason.
- [Layout and normal-driver controls](../../bench/recursion/results/recursion-region-layout-controls.json): separate controlled experiments, actual code identity and scheduler observations.
- [Corrected-source validation](../../bench/recursion/results/recursion-region-validation.json): local gates, artifact identities and the diagnostic comparison audit.

The local validation commands were `make`, the `test_typed*.py`,
`test_function_summaries.py` and `test_compiler_state*.py` unittest discovery
suites, `tools/check_ir.sh ./pystachy tests/ir/*.py`, and
`make typecheck lint-python check-runtime check-repository`. Native fixture runs
used `tests/run.sh ./pystachy "jit aot"` with the nineteen cases listed in the
validation JSON, then the recorded GC and optimization settings. The full
comparison used an instrumented copy of `tools/irsame.sh` that retained the
original compiler invocations and preserved raw messages, statuses and compressed
LLVM. Full required CI status for the publication head is recorded on
[PR #996](https://github.com/den-run-ai/pystachy/pull/996); this report does not
claim a separate full local `make verify` run.
