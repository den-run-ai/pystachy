# Recursion guard optimization, 31 October 2026

The optimized recursion guards reduce the measured cost of
[PR #996](https://github.com/den-run-ai/pystachy/pull/996) on the JSON and object
kernels after integration with merged
[PR #997](https://github.com/den-run-ai/pystachy/pull/997). The longer, warmed JSON
measurement is 0.083% above main in JIT and 1.41% above main in AOT; the object
kernel is 0.27% above main in AOT. These small elapsed-time differences are
inconclusive on this shared host. Instruction counts still show overhead:
6.34%/3.64% for JSON JIT/AOT and 8.53%/7.70% for object JIT/AOT. The ordinary-call
control retains 30.00% additional JIT instructions.

This is evidence of improvement over the original guards, with a remaining
instruction cost. It establishes neither zero overhead nor a general application
speedup. No acceptance threshold has been approved, and #996 remains draft.

## Measured sources

Three independently built variants use the same input programs and pinned
toolchain. The local checkouts reproduce the source trees below exactly. These
are the sources of the original elapsed-time and instruction-count series.

| Variant | Source revision | Git tree |
|---|---|---|
| Main, including #997 | [`06e3ad5d08514ba31fb231fe4636a962fe6578e3`](https://github.com/den-run-ai/pystachy/commit/06e3ad5d08514ba31fb231fe4636a962fe6578e3) | `db120afecf27ff03b08c25624dc64be8b06bac3b` |
| Main plus original guards and regex fallback repair | [`0166fbb556754b3d23ac68647baf458a55bd74cb`](https://github.com/den-run-ai/pystachy/commit/0166fbb556754b3d23ac68647baf458a55bd74cb) | `c2c4ffe9efdb1c9dfe9511e320cedc78ff675fac` |
| Optimized guards | [`14332cb4a658b7be33edf4f25da910e7ed4ffcb5`](https://github.com/den-run-ai/pystachy/commit/14332cb4a658b7be33edf4f25da910e7ed4ffcb5) | `7e651ca97776abe89e2919c7e2d02cddd96271b7` |

The corrected compiler is
[`3b2a66bdc6a8662beb0b4dc984bf83a65374480b`](https://github.com/den-run-ai/pystachy/commit/3b2a66bdc6a8662beb0b4dc984bf83a65374480b),
tree `b7780adc751f8ce8a840a6ea42ac6d8434f037a6`. It adds the conservative file/weakref
boundary described below and spells integer mask updates as scalar assignments
for the ownership inventory. Only `optimizations.py` changed among the 131
compiler/runtime/library/build inputs of the measured optimized variant.

A follow-up equivalence audit checked seven complete raw LLVM modules, replayed
the unchanged JIT pipeline for both sets of modules using the same stdin module
identity, and rebuilt five AOT executables. All raw IR, all seven resulting JIT
modules, all five complete executables and the subset runtime IR were byte-identical
to their corresponding references. Raw program IR was not normalized. Executable
checksums also passed. This establishes continuity of the native benchmark
programs; it is not a new elapsed-time or instruction-count measurement. The
compilation-cost section was remeasured using the corrected compiler.

All three checkouts were clean. Hashes of 131 compiler, runtime, library and
build inputs per variant were checked before and after measurement and remained
unchanged. Benchmark outputs matched CPython before timing and in every measured
execution. Earlier pre-#997 percentages, including the historical 14.5% JSON JIT
and 10.5% object AOT regressions, are historical context rather than measurements
against this main baseline.

The three sources in [bench/recursion](../../bench/recursion) are byte-for-byte
copies of the archival probes used for both the historical and current runs.
They each print one warm-up result and seven checksum/time pairs.

| Source | Elapsed-time input | Expected checksum | SHA-256 |
|---|---:|---:|---|
| [json_calls.py](../../bench/recursion/json_calls.py) | 2,000 parses of a 32-key object | 64,000 | `04a3b45405ef1b96360dbe941e072e5922d8dcae39d8a5bd45745000ea47c9fc` |
| [object_calls.py](../../bench/recursion/object_calls.py) | 100,000 iterations over 64 counters | 3,226,706,707 | `4da3eeae714a896bb205a4d16e1d91d0bafad2ec58a3dee0d33cc90096de70af` |
| [ordinary_calls.py](../../bench/recursion/ordinary_calls.py) | 10,000,000 arithmetic steps | 52,241 | `ecf346f4e65bab89564c52d864bd405641bc7689374a303b3a9f74bc8ab4df6c` |

The longer JSON measurement changes only the wrapper: it performs three extra
untimed kernel calls before the existing warm-up and runs with `n=20000`. Its
checksum is 640,000 and its source SHA-256 is
`e79db8665beceb05068395306bf3fc759ee46adc51ab483a4da3e991be61539c`.
The JSON kernel is unchanged. The exact transformation is shown below.

## What changes

The compiler separates the source-function entry check from publishing and
restoring the global recursion depth. An eligible function keeps its entry check
even when the compiler can remove its depth writes. Low recursion limits can
therefore still reject the call before its body starts.

A separate depth-observation analysis follows the existing call graph. A leaf
can omit publication only when every path, including exceptional and cleanup
paths, cannot observe the missing depth, enter another counted function, change
the limit or invoke user code. Ordinary raising and runtime-state effects remain
in the effect model. A callee's own eligibility does not make a counted call in
its caller harmless. Unknown calls, user callbacks, generators and embedding
boundaries remain conservative. In particular, the user-code effects of numeric
container equality and hashing introduced with #997 still block this proof.

The second optimization covers a restricted set of terminal paths. If every
depth-observing operation lies on paths that cannot return normally, a function
can perform its normal work after the entry check and publish depth once on the
edge into such a terminal region. Publication occurs before the first observer,
including a callback or custom exception rendering. It preserves earlier body
side effects and the original failing call. Local exception handlers and
generators are excluded. Hidden failure edges are included in the proof; an edge
that cannot safely host publication rejects the optimization. This is narrower
than general hot-region versioning, which is not implemented here.

LLVM recursion-state accesses receive alias metadata under the existing
object-field TBAA root, and the overflow call is explicitly cold. The shared root
lets LLVM distinguish recursion state from object fields. Metadata helps load
motion; it does not by itself remove the depth increments and restores. Recursive
paths and other observation boundaries retain their required accounting.

### Observable finalization boundary

The first full optimized CI run exposed a real JIT regression in the existing
`rt_list_vacated` fixture: reopening a discarded list item's buffered writer read
an empty string instead of its buffered text. Main, original guards and the same
optimized compiler with `-recursionleaf` passed; optimized AOT also passed. The
one constructor's removed bookkeeping changed the caller's native register/stack
layout enough to retain a discarded owner as a conservative GC root.

The corrected compiler therefore keeps all bookkeeping in programs that register
native `open` or any `weakref.*` operation. An unrelated leaf can change a caller's
spills too, so a constructor-only or file-operation-only restriction is insufficient.
The frontend has these registrations before the pass. Ordinary printing and
standard streams remain eligible. Generator cleanup stays a function-level
observer; collection does not close abandoned generators in the existing runtime.

Contracts prove that file/weakref programs emit exactly the guarded IR from the
same compiler with `-recursionleaf`. This preserves existing conservative-GC
semantics, including possible delayed finalization; it does not establish
CPython-style deterministic destruction. The restriction is material: an
application that combines JSON parsing with native file opening retains the
original bookkeeping cost. The pure computation kernels in this report remain
eligible, as the byte-equivalence audit confirms.

An intermediate leaf-only candidate, `3d1091ca`, measured 4.11% JSON JIT and 6.56%
JSON AOT overhead in a separate, noisy short-input series. Those values motivated
the terminal-path follow-up. They are not pooled with, or substituted for, the
final compiler snapshot measured below.

## Measurement method

Measurements ran on 31 October 2026 on Linux x86-64 with an AMD EPYC 9V74
processor, CPython 3.13.16, Ubuntu LLVM/Clang 18.1.3 and Valgrind 3.22.0. Each
process was pinned to CPU 0. Default compiler optimization settings were used.
Inherited `PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME` settings were cleared, then
the pinned LLVM directory and a private runtime cache were selected for each
variant. A trivial program warmed each runtime cache before compilation-cost
samples. No other owned heavy job ran concurrently. External shared-host load
and CPU frequency remained uncontrolled; the one-minute load average was 0.55
at the start of timing and 1.31 at the end.

For each input and mode, five rounds rotated the three variants and reversed
order on alternate rounds. Each process executed one warm-up plus seven timed
kernel calls, except the longer JSON wrapper's three additional untimed calls.
The tables use the median of the five process medians. Timers surround the
kernel only and exclude compiler startup, runtime-cache creation and AOT build
time. The hosted compiler's `run` command executed the generated code through
the actual ORC JIT; AOT used separately built native executables.

### Longer, warmed JSON elapsed time

This is a separate experiment with ten times the input and four untimed kernel
calls per process. Times are milliseconds. Parentheses give the minimum and
maximum of the five process medians, not a confidence interval.

| Mode | Main | Original guards | Optimized guards | Original / main | Optimized / main |
|---|---:|---:|---:|---:|---:|
| JIT | 55.925 (51.304–57.943) | 59.496 (55.503–60.483) | 55.972 (54.095–56.656) | +6.384% | +0.083% |
| AOT | 49.442 (46.162–53.306) | 51.408 (49.060–54.927) | 50.138 (49.363–55.058) | +3.976% | +1.409% |

The optimized medians are close to main and improve on the original-guard
medians. The overlapping ranges do not resolve the exact remaining elapsed-time
cost. The instruction counts below show that some extra work remains.

### Original-size elapsed time

These shorter calls are visibly noisy, especially JSON. They are reported
separately so the longer warm-up is not silently substituted into the historical
probe. Times are milliseconds; percentages compare with main in the same mode.

| Kernel | Mode | Main | Original guards | Optimized guards | Original / main | Optimized / main |
|---|---|---:|---:|---:|---:|---:|
| JSON | JIT | 5.613 | 6.259 | 5.765 | +11.51% | +2.70% |
| JSON | AOT | 5.107 | 5.253 | 5.663 | +2.85% | +10.88% |
| Object | JIT | 12.880 | 14.204 | 12.761 | +10.28% | -0.92% |
| Object | AOT | 10.750 | 12.165 | 10.779 | +13.16% | +0.27% |
| Ordinary | JIT | 11.403 | 12.159 | 11.425 | +6.62% | +0.19% |
| Ordinary | AOT | 9.927 | 9.716 | 9.343 | -2.12% | -5.88% |

For short JSON, main JIT process medians span 5.181–6.759 ms and optimized JIT
5.578–8.199 ms; main AOT spans 5.019–6.271 ms and optimized AOT 5.138–6.453 ms.
The short JSON AOT median therefore cannot establish a precise 10.88% regression
or be dismissed as proof of no regression. The longer-input experiment and
instruction counts provide additional, separately scoped evidence. Likewise, the
negative object/ordinary elapsed percentages are not general speedup claims.

### Dynamic instruction counts

Callgrind counts actual generated native execution. The JSON and object AOT
measurements use the exact unmodified executables from the timing run, toggling
collection on entry and return of `f.kernel`. Eight returns were verified for
each measurement. JIT uses client-request markers around each kernel invocation;
all pre-existing function bodies except the module initializer were checked
byte-for-byte against the uninstrumented version for every variant. Only the
initializer and two marker wrappers differ. Compiler, startup, timers and printing are outside
the collection interval. The marker measurements include small constant
marker/call overhead.

The ordinary AOT kernel is completely inlined and has no retained `f.kernel`
symbol. It therefore uses the same marker approach as JIT, with kernel IR
equality checked before compilation. Its AOT counts are from that instrumented
executable, not from the unmodified timed binary.

Counts below sum the warm-up and seven measured calls. JSON uses `n=2000`, object
uses `n=5000` with checksum 162,225,943, and ordinary uses `n=100000` with checksum
11,281. The smaller object/ordinary sizes bound profiling time and retain the
same kernels; do not equate their count totals with the larger elapsed-time
inputs. One process was profiled for each input, variant and mode. Counts include
the whole kernel and its runtime/GC work, not only guard instructions.
Percentages compare instruction counts within the same execution mode.

| Kernel | Mode | Main instructions | Original guards | Optimized guards | Original / main | Optimized / main |
|---|---|---:|---:|---:|---:|---:|
| JSON | JIT | 572,277,542 | 622,573,145 | 608,558,908 | +8.79% | +6.34% |
| JSON | AOT | 526,398,936 | 568,691,700 | 545,551,003 | +8.03% | +3.64% |
| Object | JIT | 90,036,184 | 115,639,360 | 97,717,792 | +28.44% | +8.53% |
| Object | AOT | 67,032,624 | 82,394,752 | 72,194,240 | +22.92% | +7.70% |
| Ordinary | JIT | 8,000,160 | 10,400,217 | 10,400,217 | +30.0001% | +30.0001% |
| Ordinary | AOT | 5,000,217 | 5,000,289 | 5,000,289 | +0.00144% | +0.00144% |

The optimized JSON and object counts are lower than the original-guard counts
in both modes, while remaining above main. The ordinary JIT result is unchanged
by this optimization. A small elapsed-time difference can coexist with a larger
instruction increase; instruction counts measure executed work, not elapsed
cycles, and do not justify a claim that all guard overhead has disappeared.

The terminal-path publication follow-up makes a smaller incremental difference
after leaf elision: JSON instructions decline from 611,134,815 to 608,558,908
in JIT (-0.42%) and from 546,574,975 to 545,551,003 in AOT (-0.19%). The two
separate noisy elapsed-time series cannot attribute all their difference to
this follow-up.

### Compilation cost and output size

The table below is a fresh batch using main, original guards and corrected
compiler `3b2a66bd`, with three rotated samples for every input/variant/stage:
72 samples in total. Each variant's private runtime cache was warmed first;
processes were pinned to CPU 0. Every emitted IR module and executable remained
byte-identical to its recorded reference. The one-minute host load was 0.35 at
the start and 1.61 at the end; external load and frequency were uncontrolled.

Cells give the median and full sample range in seconds. The hosted `ir` command
includes process startup; `build` includes frontend, LLVM work and linking. These
are not isolated frontend/backend timings, and subtraction does not provide a
reliable backend cost. Three samples are descriptive, not a precision timing gate.

| Input | Stage | Main | Original guards | Optimized guards |
|---|---|---:|---:|---:|
| JSON | IR command | 0.151 (0.150–0.161) | 0.157 (0.148–0.173) | 0.158 (0.157–0.175) |
| JSON | AOT build | 1.755 (1.746–1.870) | 1.704 (1.640–1.821) | 1.717 (1.695–1.897) |
| Object | IR command | 0.053 (0.050–0.060) | 0.056 (0.047–0.078) | 0.064 (0.051–0.065) |
| Object | AOT build | 0.387 (0.343–0.428) | 0.351 (0.349–0.507) | 0.359 (0.333–0.422) |
| Ordinary | IR command | 0.052 (0.048–0.058) | 0.055 (0.054–0.058) | 0.057 (0.049–0.062) |
| Ordinary | AOT build | 0.349 (0.348–0.394) | 0.411 (0.403–0.434) | 0.416 (0.323–0.493) |
| Longer JSON | IR command | 0.156 (0.148–0.177) | 0.142 (0.139–0.176) | 0.176 (0.145–0.185) |
| Longer JSON | AOT build | 1.872 (1.761–1.901) | 1.794 (1.636–1.881) | 1.664 (1.653–1.667) |

The ordinary AOT median rises from 0.349 to 0.416 seconds in this batch, with a
wide optimized range. Small apparent build improvements in other rows are not
established speedups. Earlier single-sample costs are historical: for example,
short JSON was 1.620/1.661/1.752 seconds before this follow-up batch.

| Input | Main / original / optimized emitted IR lines | Main / original / optimized AOT bytes |
|---|---:|---:|
| JSON | 4,154 / 4,275 / 4,289 | 153,688 / 153,856 / 153,808 |
| Object | 300 / 337 / 352 | 46,528 / 46,640 / 46,640 |
| Ordinary | 194 / 228 / 246 | 46,312 / 46,424 / 46,424 |
| Longer JSON | 4,176 / 4,297 / 4,311 | 153,688 / 153,856 / 153,808 |

The build observations show the scale of compilation and code-size changes but
are too sparse and noisy for a precise compilation-speed conclusion. JIT startup and
compilation were excluded from the kernel timer and are not separately isolated
by this report.

## Reproduction

Use separate checkouts of the three source identities above, a pinned CPython
3.13.16 and LLVM 18.1.3, and the same benchmark bytes in every checkout. Run each
command from the selected compiler's root. Avoid inherited home/path/cache,
optimization and stress overrides; give each variant its own fresh cache and
then warm it. `PROBES` points to the common copy of `bench/recursion`, and
`RESULTS` to a separate output directory for that variant. Both must be absolute
paths. The commands use the existing compiler CLI, not a new benchmark gate.

```sh
export PYSTACHY_LLVM=/path/to/llvm-18/bin
export PYSTACHY_CACHE="$RESULTS/runtime-cache"
mkdir -p "$RESULTS"
printf 'print(17)\n' > "$RESULTS/warm.py"
python3.13 -m pystachy run "$RESULTS/warm.py"

python3.13 "$PROBES/json_calls.py" 2000
taskset -c 0 python3.13 -m pystachy ir "$PROBES/json_calls.py" -o "$RESULTS/json.ll"
taskset -c 0 python3.13 -m pystachy build "$PROBES/json_calls.py" -o "$RESULTS/json"
taskset -c 0 python3.13 -m pystachy run "$PROBES/json_calls.py" 2000
taskset -c 0 "$RESULTS/json" 2000
```

Repeat with `object_calls.py 100000` and `ordinary_calls.py 10000000`, using
distinct output filenames. Verify the checksum of every kernel result. Execute
five rounds, rotating variant order and reversing it on alternate rounds, then
take the median of each process's seven times and the median of those five
medians. Do not time concurrent compiler builds or profile runs.

Generate the exact longer JSON wrapper outside the source checkout, leaving the
committed probe unchanged:

```sh
python3.13 - "$PROBES/json_calls.py" "$RESULTS/json_calls_long.py" <<'PY'
import hashlib
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text()
needle = 'print("warm", kernel(text, n))'
assert source.count(needle) == 1
source = source.replace(needle, 'for warmup in range(3):\n    kernel(text, n)\n' + needle)
data = source.encode()
assert hashlib.sha256(data).hexdigest() == "e79db8665beceb05068395306bf3fc759ee46adc51ab483a4da3e991be61539c"
Path(sys.argv[2]).write_bytes(data)
PY
```

Build/run this generated source in the same way with `20000`, and verify checksum
640,000. Keep these results separate from the original-size table.

For JSON/object AOT instruction counts, profile the **same binary** used for
timing, at the instruction-count input size above:

```sh
taskset -c 0 valgrind --tool=callgrind --error-exitcode=99 \
  --collect-atstart=no --toggle-collect=f.kernel --dump-after=f.kernel \
  --callgrind-out-file="$RESULTS/json.callgrind" "$RESULTS/json" 2000
```

Verify eight kernel-return dumps, then sum the `summary:` instruction count from
those dumps and the final profile. A missing symbol must not be treated as a
zero-cost kernel. For JIT and the inlined ordinary AOT case, insert paired
Callgrind client requests immediately around the warm-up call and each timed
kernel call in a temporary copy, and run the real `lli` process or instrumented
AOT executable under Callgrind with collection initially disabled. The helper
used for each marker is `void count_start(void) { CALLGRIND_TOGGLE_COLLECT; }`
and an identical `count_stop`, compiled with `-O2 -shared -fPIC` against
`valgrind/callgrind.h` and declared through `ffi.extern`. Place timers and
printing outside the markers. Compare all pre-existing emitted function bodies
except the module initializer against the original before accepting an
instrumented count. Include all eight
invocations and record the constant marker overhead in the scope description.

## Correctness and verification scope

The regex repair catches `RecursionError` only around the generated match/search
invocation and translates it into specialization decline. State reset and
interpreter fallback remain outside the catch. A failure from the interpreter
or a replacement callback therefore still propagates. The focused regression
covers match/search at ordinary and lowered limits, deeper callers, capture
variants and replacement-callback exceptions.

The measured compiler passed twelve focused recursion/regex fixtures in native
JIT and AOT using the hosted compiler: 24 executions. The same suite passed
under program GC stress (24 executions), with all optimizer passes disabled
(24 executions), and with JIT inlining disabled (12 JIT executions). These
checks exercise entry-limit behavior, side effects before failing calls, limit
changes, recovery, uncaught custom exception rendering, and generator
resume/throw/close. The regex repair also passed 15 hosted specialization tests;
independently removing either generated-invocation catch made its negative
control fail as expected.

All 43 IR contract probes passed hosted generation and LLVM 18 assembly, and
the runtime contract check passed 598 entries, 70 exception classes and 172
subset functions. The local evidence is focused validation; it is not the full
final-tree matrix. That compiler also passed a 792,014-line self-hosting fixed
point, an 18,805-line runtime fixed point, and all 24 focused executions using
the resulting native compiler. A 3,913-case native compilation comparison found
no changed statuses or new rejections, but preceded the finalizer safeguard.

The corrected compiler passed 20 recursion proof/CFG contracts and the unchanged
file-finalization fixture plus weakref transition/callback fixtures in JIT/AOT,
normally and with program GC stress: 12 executions. File and weakref IR-equality
contracts and a positive stdout-only leaf control cover the new boundary.
Mypy passed all 48 source files. The corrected self-hosting, complete local
comparison and CI results are recorded separately in the PR when complete.

The upstream original-guard head `0166fbb5` completed 59 successful checks with
two expected skips and no failures. Its
[CI run](https://github.com/den-run-ai/pystachy/actions/runs/41153334248) and
[coverage run](https://github.com/den-run-ai/pystachy/actions/runs/41153334286)
include the regex fallback repair. They precede this optimization and do not
validate the optimizer. The first optimized head, `e4a313db`, completed with 46
successful checks, 11 failed checks and four skips. Its failures had three causes:
the cache test's exhaustive disabled-pass list omitted `recursionleaf`; the
ownership inventory treated integer augmented assignment as a container write;
and the file-finalization mismatch above failed seven jobs. The combined gate
also failed, and two coverage reports were blocked. The corrected source fixes
all three causes without changing expected program output. Fresh combined-tree
validation remains required before a merge-ready claim; see the PR for its latest
completed checks.

The remaining performance question is the nonzero instruction cost, including
the unchanged ordinary JIT control. The measured scope is three kernels on one
Linux host. A broader guard transformation must preserve callback and limit
observability and the ordering of side effects before a failing call; this
report does not authorize a weaker recursion contract to meet a timing target.
