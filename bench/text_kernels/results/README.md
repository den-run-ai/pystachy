# Text-kernel prototype results

Measured on 2026-11-06 from base `f7103067545b43cdcd8ce20dc66b1571425b3a8d`
plus this prototype. Both compile-time switches remain off by default.

The bounded float path removes a temporary buffer from ordinary terminated ASCII
numbers and is the stronger candidate for further integration. The StringZilla
adapter works against the real pinned dependency and preserves the tested JSON
Unicode/error positions. Its benefit depends on the input; this run does not
establish a general JSON speedup or justify making the dependency mandatory.

## What was measured

The machine reports an AMD EPYC 9V74 80-Core Processor, Linux x86-64, glibc 2.39,
clang/LLVM 18.1.3 and CPython 3.13.16. Each native process was pinned to logical CPU
0. Work in this task used a shared exclusive build/benchmark lock; the host itself
was not dedicated. The selected adapter backend was `haswell-avx2`.

Four builds used the same compiler, sources and workload inputs: both switches
unset, `PYSTACHY_FLOAT_SPAN`, `PYSTACHY_STRINGZILLA`, and both. Each had an independent
fresh runtime cache. The first fixture build includes cold runtime-cache creation;
the workload builds reuse that variant's runtime cache. The benchmark then ran
five separate processes per case/variant, rotating variant order. Each process
performs a first batch, one warmup batch and one measured batch. Only the internal
measured batch is in the timing table. All non-clock output fields were compared
with CPython before accepting each of the 320 timing samples.

The JSON consumer is the existing complete decoder and maintained repair facade
in [`../../extended/json_scan.py`](../../extended/json_scan.py). Its repair rows
exercise the facade on valid JSON, including its decoder fast path; they do not
measure repair of every malformed JSON grammar. The numeric consumer splits a
comma-separated batch, parses every field, and computes a weighted score. Expected
scores use binary-exact values and are checked before/after each workload.

[`timings.json`](timings.json) preserves every raw timing, every output witness,
minima/maxima, build measurements, dependency/header hashes, compiler hash and
hashes of the measured prototype sources. Its source-head field identifies the
base because measurement preceded the prototype commit. Report and review-helper
files added afterwards are not claimed to be part of that measurement snapshot.
Unchanged compiler, runtime Python, library and port code are identified by the
base commit; the compact manifest retains the relevant measured files.

## Workload timings

Values are median milliseconds per complete batch. Smaller values mean less elapsed
time. The input size and exact call count are preserved in each raw witness. JSON
short uses 100,000 calls, long/sparse 2,000, Unicode 150 and dense escapes 300.
Numeric short uses 200,000 four-field calls; other cases use 256-field batches,
with 3,000 calls for plain/trimmed and 1,000 for long/underscores/Unicode.

| Workload | Baseline ms | Float span ms | StringZilla ms | Combined ms |
|---|---:|---:|---:|---:|
| json-direct-short | 42.973 | 39.633 | 47.474 | 37.811 |
| json-direct-long | 18.523 | 15.390 | 12.304 | 12.935 |
| json-direct-unicode | 5.065 | 4.596 | 4.435 | 4.387 |
| json-direct-sparse | 28.660 | 19.539 | 18.746 | 24.844 |
| json-direct-dense | 2.124 | 2.279 | 2.015 | 2.035 |
| json-repair-short | 52.784 | 54.434 | 39.589 | 51.891 |
| json-repair-long | 14.737 | 14.607 | 12.342 | 14.306 |
| json-repair-unicode | 4.920 | 5.227 | 4.911 | 5.018 |
| json-repair-sparse | 20.054 | 22.415 | 16.929 | 17.644 |
| json-repair-dense | 1.786 | 2.027 | 1.698 | 2.346 |
| numeric-short | 82.603 | 66.730 | 84.622 | 52.395 |
| numeric-plain | 73.253 | 48.449 | 81.343 | 48.775 |
| numeric-long | 238.139 | 60.578 | 227.076 | 67.993 |
| numeric-trimmed | 91.561 | 65.860 | 86.252 | 79.635 |
| numeric-underscores | 42.580 | 28.207 | 40.457 | 25.469 |
| numeric-unicode | 50.541 | 43.240 | 39.892 | 31.285 |

Long numeric ingestion had a baseline median of 238.139 ms and float-only median
of 60.578 ms (3.93 times as much throughput for the same batch). All five baseline
samples were 232.308–312.242 ms; all five float-only samples were 59.203–67.638 ms.
This is the clearest timing signal. Plain numeric ingestion's median improved
from 73.253 to 48.449 ms, but its ranges overlap, so the exact 1.51 ratio is an
observation from this run rather than a stable performance promise.

For long JSON decoding, the baseline/StringZilla medians were 18.523/12.304 ms;
the ranges overlap at 14.622–26.681 and 11.807–20.097 ms. Short JSON did not call the
external scan and still varied materially. The float-only build also changed some
string-only JSON medians despite not exercising the float optimization. These
controls show why small ratios and several apparent combined-build effects cannot
be attributed reliably to a kernel change. Dense-escape batches lasted only about
2 ms and had particularly wide variation. All samples are retained, including
regressions; no timing threshold is used as a test.

## Complete-process instruction counts

Because timing dispersion was material, the same hash-verified native binaries
were replayed under Valgrind 3.22 Callgrind. These are whole-process `Ir` counts,
including startup, input preparation, validation, the first batch and one timed
batch with no warmup. Wall-clock fields from instrumented execution are discarded.
Every output witness still matched CPython. A separate linked probe confirmed
`haswell-avx2` both natively and inside Callgrind against the exact adapter bytes;
[`backend.json`](backend.json) retains the commands, versions and hashes.
This is a separate workload size from
the native timing experiment: JSON short/long/Unicode use 10,000/1,000/150 calls;
numeric plain/long/underscores use 200/100/100 calls per batch.

| Workload | Baseline instructions | Float span | StringZilla | Combined |
|---|---:|---:|---:|---:|
| json-direct-short | 58,300,216 | 58,300,264 | 58,345,106 | 58,341,548 |
| json-direct-long | 234,486,582 | 234,486,596 | 192,357,613 | 192,610,310 |
| json-direct-unicode | 170,605,657 | 170,605,731 | 162,971,322 | 162,718,532 |
| numeric-plain | 132,618,822 | 101,862,082 | 132,868,018 | 101,880,796 |
| numeric-long | 514,867,742 | 161,809,921 | 514,910,842 | 161,852,806 |
| numeric-underscores | 107,337,854 | 80,190,814 | 107,150,470 | 80,233,677 |

Float-only instruction counts fell 23.2% for plain numeric ingestion, 68.6% for
long numbers and 25.3% for underscored numbers. The unrelated JSON controls in the
float-only build changed by fewer than 100 instructions per process. This supports
the parser mechanism while giving no reason to attribute the noisy JSON timing
changes to float parsing.

StringZilla reduced complete-process instruction counts by 18.0% for long JSON
and 4.5% for Unicode JSON. Short JSON, which keeps the portable scan, changed by
about +0.077%, including the extra shared-library startup. Whole-process counts do
not measure cycles, cache misses or vector-lane utilization; they establish less
executed instruction work for these particular consumers.

[`instructions.json`](instructions.json) preserves all 24 counts, exact commands,
executable hashes and CPython witnesses. Its `native_results_sha256` matches the
`original_results_sha256` retained in the compact native timing record.

## Copies and allocation requests

The untimed native probes include the real runtime. `FLOAT_PARSE_COPY` counts bytes
submitted to parser copies, including the terminating NUL. It excludes Unicode
normalization and the control's internal buffer-growth recopy. `GC_RAW_REQUEST`
counts actual raw allocation requests during the ASCII parser call, after input
construction. Requested capacity is distinct from physical allocator size-class
rounding, retained heap, peak RSS and the collector's pacing credits.

| Input | Baseline copied bytes | Float-span copied bytes | Baseline raw requests / bytes | Float-span raw requests / bytes |
|---|---:|---:|---:|---:|
| `12.5` | 5 | 0 | 1 / 65 | 0 / 0 |
| two spaces then `-0` | 3 | 0 | 1 / 65 | 0 / 0 |
| `12.5` then space/tab | 5 | 5 | 1 / 65 | 1 / 68 |
| `1_2.5` | 5 | 5 | 1 / 65 | 1 / 6 |
| `+InF` | 5 | 0 | 1 / 65 | 0 / 0 |
| `1e-9999` | 8 | 0 | 1 / 65 | 0 / 0 |

The trailing-whitespace path performs one bounded span copy, using the existing
buffer helper; it does not minimize requested capacity. Underscores still require
filtering, but the buffer is reserved once. Unicode conversion remains the existing
`asciinum` operation, so zero-copy claims apply to suitable ASCII input only.

The scanner probe confirms that a 4,096/8,192/16,384-byte ordinary JSON span uses
512/1,024/2,048 portable word probes in the baseline and exactly one external
StringZilla call in the optional build. Both paths also pass the no-allocation
check under GC stress. These counters establish that the intended path ran; they
do not claim that an external call is one machine instruction.

Raw evidence: [baseline float probe](baseline-float_probe.txt),
[combined float probe](combined-float_probe.txt),
[baseline scan probe](baseline-bytescanprobe.txt), and
[combined scan probe](combined-bytescanprobe.txt).

## Build and deployment cost

These are single build observations, not distributions. Times include the build
command and its bookkeeping; cache state is specified above. File sizes are
unstripped executable/shared-object bytes, not resident-memory measurements.

| Variant | JSON executable bytes | Numeric executable bytes | Additional adapter bytes | First cold fixture build s | Warm JSON build s | Warm numeric build s |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 440792 | 120936 | 0 | 6.732 | 6.534 | 1.404 |
| float_span | 440792 | 120936 | 0 | 6.618 | 6.762 | 1.175 |
| stringzilla | 440880 | 120936 | 19736 | 6.675 | 6.234 | 1.220 |
| combined | 440880 | 120936 | 19736 | 6.596 | 5.997 | 1.262 |

Building and loading the pinned adapter took 0.287 s. The JSON optional executable
plus adapter is 460,616 bytes versus 440,792 bytes for the baseline, a 19,824-byte
increase (about 4.50%). The current flags also give the numeric executable an ELF
`DT_NEEDED` entry for `libtextkernels.so`, even though that workload does not use
JSON scanning; its deployed bundle is therefore 140,672 rather than 120,936 bytes.
A production integration should link the dependency only when needed. The complete
upstream license must accompany redistribution of the optional shared object.

The prototype keeps CPU-specific code in the shared object to avoid the compiler
driver's runtime target-attribute normalization. Its absolute run-specific RPATH is
for reproducible experiment builds. Production packaging and static integration
remain separate work. The existing AOT execution model is retained.

## Correctness evidence and remaining gates

* The default compiler bootstrap reached identical stage-1/stage-2 compiler IR
  (832,277 lines) and runtime-Python IR (18,805 lines).
* Both committed regression fixtures matched pinned CPython byte-for-byte in AOT,
  JIT and AOT with GC stress, for each of the four variants: 24 comparisons.
* The native scan probe passed 5,737,092 scalar-oracle/bounds checks per execution,
  in the baseline and combined builds, both normally and with GC stress. It covers
  every byte, alignment, competing stop positions, predicates, short/long spans,
  invalid wrapper ranges and protected pages directly beside readable spans.
* The float probe passed 64 naturally aligned exact-terminator guard-page cases
  in both builds, plus the copy/allocation and signed-zero checks above.
* Independent review compared 2,281 generated float cases against CPython, the
  baseline, and the float path in AOT/JIT/stressed AOT, including exact exception
  messages and signed NaN/zero. The compact deterministic generator and output
  hashes are retained in [float-review.json](float-review.json). That review
  preceded addition of the default-no-op allocation-accounting hook.

* Final `make check-fast check-runtime lint` passed: 415 hosted tests, Ruff,
  mypy (49 source files), repository hygiene, ShellCheck, native C warning checks,
  644 runtime entries / 70 exception classes / 172 runtime-Python functions,
  and 67 static pointer stores with no GC root problems. Both new fixtures also
  passed the IR checker and `llvm-as`. The dedicated float probe passed warning
  checks both with the switches unset and with both enabled. The exact final
  output is retained in [validation.txt](validation.txt).
* The independent adapter helper passed another 36,787 protected-page cases per
  backend over 271 lengths up to 4,096 bytes, for both the measured
  [AVX2 library](adapter-bounds-avx2.json) and a separately built
  [serial library](adapter-bounds-serial.json). These are correctness checks;
  serial performance was not measured.

The full release validation matrix, remote CI, other platforms/ISAs and static
linking are not established by this experiment. Its current status is a draft
prototype. The two switches remain independent and optional. The float path is
ready for broader differential evaluation and representative consumer trials;
StringZilla should retain a measured workload threshold and deployment decision.

## Reproduce

Follow [`../README.md`](../README.md) for the pinned source, compiler and complete
four-variant runner. The full runner creates its own fresh dependency snapshot,
private caches, command log, binaries and raw results. Independent review helpers
are in `tools/text_kernels`; the recorded generator seed is 710655582.
