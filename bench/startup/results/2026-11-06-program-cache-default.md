# Default native program cache: launch costs and validation, 2026-11-06

## Latest corrected implementation: 9a3cc059

The latest measurements in this report use
[`9a3cc0594ed2d5d638e2278478c1aa9256557aac`](https://github.com/den-run-ai/pystachy/tree/9a3cc0594ed2d5d638e2278478c1aa9256557aac),
which fixes duplicate static-input capture across the two-second settling
threshold. This is the implementation measured for promotion in
[PR #1103](https://github.com/den-run-ai/pystachy/pull/1103) and
[#104](https://github.com/den-run-ai/pystachy/issues/104).
The earlier `e3b1b3a8` measurements and validation remain explicitly historical
below; their raw files and original validation fields are preserved.

**Latest measured result:** five interleaved rounds produced a
38.75x median paired speedup for the import-heavy command
(1.625565 s uncached median,
0.039795 s hit median), and
31.13x for the complete 1,000-event router command
(1.224718 s to
0.040723 s). The padded-helper command improved
2.16x. All 20 timed hits skipped both the frontend and LLVM.

**Tiny-command results vary across runs.** This refresh measured
45.842 ms uncached versus
41.920 ms for a hit
(1.06x median paired speedup; 3/5 pairs faster).
The preserved `e3b1b3a8` run measured 33.227 ms uncached versus 36.319 ms for a
hit: 0.93x and a 3.092 ms regression, with all five pairs slower.
The six-line correction changes capture on misses, so the changed hit result
is not evidence of a performance improvement caused by that fix. This was one
prescribed five-round refresh to pin evidence to corrected code, not a search
for favorable samples. These results establish no universal startup gain;
`PYSTACHY_PROGRAM_CACHE=0` remains available.

Latest local validation completed successfully. Final-head CI is
**not evaluated by this local evidence bundle**; follow the
[PR checks](https://github.com/den-run-ai/pystachy/pull/1103/checks) for the actual
outcome. Earlier CI failures and cancellations remain recorded below.

### Latest pinned inputs

| Item | Latest value |
|---|---|
| Measured code commit | `9a3cc0594ed2d5d638e2278478c1aa9256557aac` |
| Measured code tree | `32800654827cd3edc1ecf43f7419c09ab4cb507a` |
| Native compiler SHA-256 | `4730996f292007b7b89de26a5ee2a6a186f7b012ce762d6693fa5e9b4a986c8e` |
| Platform | Linux-6.18.57-x86_64-with-glibc2.39 |
| Hosted Python | CPython 3.13.16 |
| LLVM | Ubuntu LLVM 18.1.3 (1ubuntu1), matching all five tools |
| Timing repetitions and affinity | Five interleaved rounds per workload; CPU 0 |
| Latest correctness evidence | [2026-11-06-program-cache-default-9a3cc059-checks.json](2026-11-06-program-cache-default-9a3cc059-checks.json) |
| Latest timing evidence | [2026-11-06-program-cache-default-9a3cc059-times.json](2026-11-06-program-cache-default-9a3cc059-times.json) |
| Correction, logs and native negative control | [2026-11-06-program-cache-default-9a3cc059-validation.json](2026-11-06-program-cache-default-9a3cc059-validation.json) |
| Release test archive | `pystachy-native-cache-settle-fix-linux-x86_64.tar.gz` |
| Archive SHA-256 | `fd80e80713a7cc11ca4f0ed229271b9cc1d77b14c51b0bfb6c5600bba1e46182` |

Both new raw probes report `completed: true`, `passed: true`, no setup error and
the compiler hash above. The source pin identifies the implementation; later
report-only publication commits do not become the measured code identity.

### Latest measured costs

Workload and fresh-process boundaries are unchanged: uncached runs have warm
runtime artifacts; recurring misses retain static hashes and runtime artifacts
while removing program entries; hits validate and execute afresh. First-use
fills empty `program-v2`, including its hash memo, with both runtime lineages
already warm. There is no operating-system page-cache flush. Prebuilt AOT uses
ordinary `pystachy build` and excludes build time.

Tool-count wrappers and cache tracing remain enabled. Only cache trace lines
are removed for output comparison; stdout, ordinary stderr and status must
agree with CPython. Detailed workload definitions and cache-state boundaries
are retained in the methodology below and in both raw probes.

All table times are seconds. Paired speedup is the median of the five
`uncached[i] / hit[i]` ratios, not a ratio of the displayed medians.
Ranges are observed minimum/maximum values, not confidence intervals.

| Workload | Uncached median | Recurring miss median | Hit median | Prebuilt AOT median | Median paired speedup |
|---|---:|---:|---:|---:|---:|
| Tiny | 0.045842 | 0.510070 | 0.041920 | 0.001999 | 1.06x |
| Padded helper | 0.081506 | 0.508425 | 0.037702 | 0.001947 | 2.16x |
| Import heavy | 1.625565 | 2.052534 | 0.039795 | 0.001808 | 38.75x |
| Router, 1,000 events | 1.224718 | 1.738869 | 0.040723 | 0.002312 | 31.13x |

| Workload | Uncached range | Recurring miss range | Hit range | Prebuilt AOT range | Paired speedup range |
|---|---:|---:|---:|---:|---:|
| Tiny | 0.044011-0.048826 | 0.495030-0.517632 | 0.036033-0.058247 | 0.000785-0.002281 | 0.79-1.26x |
| Padded helper | 0.076479-0.086533 | 0.476062-0.611048 | 0.034921-0.053198 | 0.000828-0.002458 | 1.53-2.43x |
| Import heavy | 1.542091-1.675805 | 1.939792-2.339000 | 0.038573-0.061257 | 0.001130-0.002434 | 27.36-41.59x |
| Router, 1,000 events | 1.155193-1.425847 | 1.590146-1.822029 | 0.039342-0.042844 | 0.001395-0.002640 | 29.04-33.57x |

First fills and AOT builds have one sample per workload. The recurring-miss
premium is the difference between its median and the uncached median.

| Workload | First-use fill, runtime warm | Ordinary AOT build | Recurring miss premium |
|---|---:|---:|---:|
| Tiny | 0.683090 | 0.347781 | +0.464229 |
| Padded helper | 0.741112 | 0.365347 | +0.426920 |
| Import heavy | 2.275479 | 6.456398 | +0.426969 |
| Router, 1,000 events | 1.810763 | 5.275301 | +0.514151 |

The timing probe passed **328 assertions**. Each of the 20 timed hits recorded
exactly one `hit` event, no frontend event, zero LLVM tool calls, exit zero and
no timeout. Every measured execution matched its CPython oracle. These are
complete-command launch measurements, not long-running application benchmarks.
The earlier and latest runs occurred separately; their absolute timings are
not a controlled before/after comparison.

### Latest completed local validation

| Check | Result at the corrected implementation |
|---|---|
| Native compiler self-build | Three-stage fixed point: 846,369 IR lines. |
| Runtime self-build | Three-stage fixed point: 18,805 IR lines. |
| Focused cache units | 143 total: 142 passed, one wrong-owner fixture skipped. Program-cache tests: 88 passed/one skipped; cached-run tests: 30 passed; toolchain tests: 24 passed. |
| Compiler-state controls | 121 passed. With the focused cache units: 264 total, 263 passed, one skipped, zero failed. |
| Native settling-threshold regression | Old module revision: three expected validity/publication/hit failures; fixed revision: all 17 assertions pass. Static/source mutation controls pass in both. |
| Default native cache probe | 498 assertions passed across all 14 groups. |
| Output-checked timing probe | 328 assertions passed; 20/20 timed hits skip frontend and LLVM. |
| Fast lint/static checks | Ruff, mypy (52 source files), repository hygiene and selected units, static GC roots, ShellCheck and C syntax checks passed. This is not the entire CI Lint workflow. |
| Relocated release smoke | Passed with inherited `LD_LIBRARY_PATH`: version checks, default fill/hit, ordinary and GC-stressed JIT/AOT, and warm ordinary-runtime reuse. Relocated read-only resources, Python-free PATH and external cache. |
| Broad corpus, pinned-base IR, full runtime contracts, existing runtime-cache suites and CPython recordings | Historical local results remain below; they were not rerun as latest local gates and are not relabeled as `9a3cc059` results. |
| Final-head CI | Not evaluated by this local bundle; use the actual [PR checks](https://github.com/den-run-ai/pystachy/pull/1103/checks) on the final published head. |

The skipped ownership fixture cannot change its file owner to UID 1 in this
user namespace (`EINVAL`); it is not counted as a pass. The latest bundle
retains exact commands, expected and actual statuses, logs and hashes. The
negative control's expected exit of 1 is retained, with its three failed
assertions identified rather than counted as ordinary passes.

Across the compiler, runtime and library implementation, the change from
`e3b1b3a8` to `9a3cc059` is six added lines in
`src/pystachy_compiler/program_cache.py`. Compiler lowering and runtime/library
sources are otherwise unchanged. The earlier broad comparisons remain pinned
to their actual run identities despite that narrow implementation change.

### Confirmed static-snapshot correction

`tool_inputs()` records the compiler before and after hashing loaded libraries.
A freshly extracted or chmodded compiler can cross the two-second settling
threshold between those reads. Previously, identical canonical path, stat tuple
and content digest could be recorded first with settled flag `0`, then with
flag `1`. The differing policy field incorrectly invalidated the capture.

The correction validates an already-recorded path against its first snapshot
and retains that snapshot. A capture made while timestamps were unsettled keeps
its content checks. Actual metadata changes and changed bytes within a simulated
coarse timestamp still invalidate publication.

The native fixture deliberately waits 2.1 seconds after its first capture and
asserts that the threshold was crossed. The current native compiler executes
the identical fixture against isolated old (`5ed9fcbc`) and corrected
(`9a3cc059`) module sources. The old variant exits 1 with exactly three
failures out of 17: unchanged-capture validity, publication and hit. The fixed
variant exits 0 with all 17 passing. Both reject real static/source changes.
The `/usr/bin/true` payload tests publication/lookup and is never executed.
The bundle retains the full fixture, both logs, the module revision/hash
manifest and invocation metadata.

### Previous CI findings and publication gates

The initial `1a33fcf1` Linux distribution failure was the inherited loader
environment mismatch described in the historical section. After that fixture
correction, the
[`5ed9fcbc` Linux distribution job](https://github.com/den-run-ai/pystachy/actions/runs/42310101672/job/128212329033)
entered `miss` and `frontend`, then reported `bypass native artifact unavailable`
with correct output and exit status zero. That trace is consistent with the
confirmed static-capture defect. The defect and fix are reproduced directly;
attribution of that particular CI event remains an inference. A later successful
distribution run would validate the corrected head; it would not reconstruct the
old trace's inaccessible internal state.

The same head's
[native-1 job](https://github.com/den-run-ai/pystachy/actions/runs/42310101672/job/128212329286)
was cancelled at the configured 15-minute boundary after its artifact recorded
3,330 passed checks and zero failures. Native-0 recorded 3,328 passes. The
retained analysis verifies that the disjoint 2,073-case selections cover all
4,146 corpus cases, with 6,658 expected checks intact. Passing artifacts do not
make a cancelled job successful.

The shards' median program times differed by 1.63x; runner-speed variation and
case mix were not independently measured. A normalized scheduling study modeled
only about 2.08% improvement from filling missing weights (2.45% from a full
refresh), establishing no new timeout bound. No CI weights, timeouts, worker
counts, job counts or corpus selections were changed in response to the
cancellation. This corpus invocation bypassed
program caching through compiler diagnostics; cache fills do not explain its
duration. A successful new native-1 job and distribution job remain required.

### Reproduce the latest measurements

Use the supported environment from [installation](../../../docs/install.md).
The raw evidence retains exact host paths; the following uses a standard LLVM
installation. Validate before timing, without an intentional concurrent
bootstrap or other heavy workload.

```sh
git checkout 9a3cc0594ed2d5d638e2278478c1aa9256557aac
export PY=python3.13
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin
make pystachy PY="$PY"
sha256sum ./pystachy

"$PY" -m unittest discover -s tools -p 'test_program_cache*.py'
"$PY" -m unittest discover -s tools -p 'test_cached_run*.py'
"$PY" -m unittest discover -s tools -p test_cache_toolchain.py
"$PY" -m unittest discover -s tools -p 'test_compiler_state*.py'

"$PY" tools/program_cache_probe.py --compiler ./pystachy --python "$PY" --llvm "$PYSTACHY_LLVM" --output build/program-cache-default-9a3cc059-checks.json
"$PY" tools/program_cache_probe.py --compiler ./pystachy --python "$PY" --llvm "$PYSTACHY_LLVM" --benchmark-only --rounds 5 --cpu 0 --output build/program-cache-default-9a3cc059-times.json
```

Choose an allowed CPU if CPU 0 is unavailable and record that change. Preserve
all rounds and the stated cache-state boundaries. The latest validation bundle
also retains release commands, the native regression fixture and orchestrator
source. Require complete, passing output-checked probes before quoting new
measurements.

## Historical candidate evidence: e3b1b3a8

Everything below records the earlier `e3b1b3a8` implementation unless a later
test-fixture-only revision is explicitly named. These measurements, logs and
comparison outcomes are historical evidence, not latest-code reruns. Original
raw checks, times and profile files are byte-for-byte unchanged. Original
validation fields are unchanged, with only a linked
`static_snapshot_correction_9a3cc059` supplement appended.

This historical section records the earlier default-enabled cache candidate for
[#104](https://github.com/den-run-ai/pystachy/issues/104) at
[`e3b1b3a8d4ee810cb8215fd986f9e83526f71dba`](https://github.com/den-run-ai/pystachy/tree/e3b1b3a8d4ee810cb8215fd986f9e83526f71dba).
A validated hit starts the saved native program afresh, preserving its current
arguments, stdin, environment and effects while skipping the frontend and LLVM.
The earlier [opt-in prototype report](2026-11-06-program-cache.md) remains
historical evidence; its measurements and validation results have not been
relabelled as results for this candidate.

**Measured result:** in five interleaved rounds, the import-heavy command fell
from a 1.457252 s uncached median to a 0.040346 s hit median, with a 36.31x median
paired speedup. The complete 1,000-event router command fell from 1.158169 s to
0.039158 s, with a 31.82x paired speedup. The 600-helper probe improved 2.10x.
All 20 timed hits entered neither the frontend nor any wrapped LLVM tool.

**The tiny program is slower with caching:** its hit median is 36.319 ms versus
33.227 ms uncached, a 3.092 ms increase, and its median paired speedup is 0.93x.
Every recorded tiny-program pair is slower with the cache. Input validation and
startup still cost more than the frontend/backend work avoided for this case.
`PYSTACHY_PROGRAM_CACHE=0` selects ordinary compilation when that tradeoff is
preferable.

First fills with runtime artifacts already warm took 0.604-2.092 s. Recurring
program misses were 0.381-0.418 s slower than ordinary uncached launches by
difference of medians. Prebuilt AOT controls started in roughly 0.9-2.3 ms.
These results support repeated commands with meaningful compilation costs;
they do not establish a universal startup improvement or a long-running
application speedup. The validation table below records the completed local
checks, including the broad default-mode corpus, and keeps PR CI as a separate
required gate.

### Pinned inputs and evidence

| Item | Value |
|---|---|
| Measured code commit | `e3b1b3a8d4ee810cb8215fd986f9e83526f71dba` |
| Measured code tree | `f6ab52f8b3ea8c93bdaf12a34feed107517ecbbb` |
| Native compiler SHA-256, both historical probes | `ed36895dd2e15bdc5a9f88de553e19cfe51ab42d5d04d6c39941bf79b202ab21` |
| Validation checkout after fixture correction | `4a18e825a3d9e4a827fd722d8c08697cc84f7f1a` |
| Corrected validation tree | `75c5f61b3146de1d4ce6b1d3f43a7317f2f6a9d1` |
| Release smoke test archive | `pystachy-native-cache-default-test-linux-x86_64.tar.gz` |
| Test archive SHA-256 | `a649b0435843a48f9a0fdc1604880e3d95ca8186fd0af6b77ed28071b0936bf7` |
| Platform | Linux 6.18.57, x86-64, glibc 2.39 |
| Hosted Python | CPython 3.13.16 |
| LLVM | Ubuntu LLVM 18.1.3 (`1ubuntu1`), matching `clang`, `opt`, `lli`, `llvm-link` and `llvm-as` |
| Timing repetitions and affinity | Five interleaved rounds per workload; process and children pinned to CPU 0 |
| First-fill repetitions | One separate first-use sample per workload |
| Correctness evidence | [2026-11-06-program-cache-default-checks.json](2026-11-06-program-cache-default-checks.json) |
| Timing evidence | [2026-11-06-program-cache-default-times.json](2026-11-06-program-cache-default-times.json) |
| Validation logs and full IR-diff review | [2026-11-06-program-cache-default-validation.json](2026-11-06-program-cache-default-validation.json) |
| Earlier diagnostic profile | [2026-11-06-program-cache-default-profile.json](2026-11-06-program-cache-default-profile.json) |

The historical correctness and timing JSON both identify the compiler hash above,
have `completed: true` and `passed: true`, and have no setup error. The source
commit and tree identify the implementation, while the binary hash identifies
the native compiler actually executed. The diagnostic profile uses an earlier
source and binary, identified separately below.

The validation checkout adds only a `tests/cache.sh` fixture correction to the
measured code commit. Compiler/runtime/library implementation files and the
measured native compiler remain unchanged. The performance JSON stays pinned to
`e3b1b3a8`; the later checkout records the corrected test harness, not a new
performance sample.

The release test archive's manifest records target `linux-x86_64`, version
`native-cache-default-test`, the measured code commit and the same native
compiler hash. Its smoke-test outcome is recorded in the validation table.

### Measurement boundary

The [probe](../../../tools/program_cache_probe.py) measures complete fresh
process launches. It compares outputs and status with CPython, warms the ordinary
runtime cache with caching disabled, builds the AOT control, and separately warms
the runtime lineage keyed by checked program-cache inputs before measuring.

| Mode | Included work and cache state |
|---|---|
| Uncached run | `PYSTACHY_PROGRAM_CACHE=0`; runtime artifacts warm. Includes the frontend, LLVM and execution. |
| Recurring program miss | Program manifests, executables and staging removed; static hashes, lock buckets and runtime artifacts retained. Includes discovery, validation, compilation, linking, publication and execution. |
| Validated hit | Fresh process immediately after an output-checked miss. Includes source/input validation, executable checksumming and fresh program execution. |
| Prebuilt AOT | Fresh launch of an ordinary `pystachy build` executable. Build time is excluded from launch time and reported separately. |
| First-use fill | Entire `program-v2` subtree empty, including the static hash memo, but both runtime lineages warm. Includes initial toolchain discovery and hashing. |

Neither a recurring miss nor the first-use fill is a cold runtime or a flushed
operating-system page cache. No page-cache flush is performed. All four first-use
samples invoked seven `clang` commands and one `opt`, with zero `llvm-as` calls;
the probe explicitly rejects first-use samples that rebuild the runtime.

Each round orders the uncached control, miss/hit pair and AOT control together;
alternate rounds reverse the outer controls. The miss and hit remain adjacent.
Medians below use all five samples. Paired speedup is the median of
`uncached[i] / hit[i]`, not the ratio of the two reported medians. Observed ranges
are minimum and maximum samples, not confidence intervals.

Only cache diagnostic traces are removed when comparing stderr. Status, stdout
and ordinary stderr must match. Transparent wrappers count calls to all five
LLVM tools, and their actual tools and loaded libraries are explicitly declared
as cache inputs. Trace and wrappers remain enabled during timing, so the results
include that instrumentation and any wrapper overhead in modes that invoke LLVM.

### Workloads and measured costs

| Workload | Exact scope |
|---|---|
| Tiny | `print(1)`; principally process startup and compilation overhead. |
| Padded helper | 600 annotated helper definitions and one live call, `helper_599(4)`. |
| Import heavy | Imports and uses `re`, `textwrap`, `json` and `fnmatch` with small deterministic inputs. |
| Router | `examples/route/route.py`, 1,000 events, three rules, four event names, `--names`, ordinary streaming path. |

Generated sources, hashes, arguments, observed output, status, traces, tool counts
and raw samples are retained in the timing JSON. All times in the following
tables are seconds, rounded to six decimal places; that formatting does not imply
microsecond measurement accuracy. No timing threshold is a correctness gate.

| Workload | Uncached median | Recurring miss median | Hit median | Prebuilt AOT median | Median paired speedup |
|---|---:|---:|---:|---:|---:|
| Tiny | 0.033227 | 0.414444 | 0.036319 | 0.000893 | 0.93x |
| Padded helper | 0.082328 | 0.491926 | 0.039425 | 0.001969 | 2.10x |
| Import heavy | 1.457252 | 1.840438 | 0.040346 | 0.002264 | 36.31x |
| Router, 1,000 events | 1.158169 | 1.576574 | 0.039158 | 0.002339 | 31.82x |

Observed five-sample ranges:

| Workload | Uncached range | Recurring miss range | Hit range | Prebuilt AOT range | Paired speedup range |
|---|---:|---:|---:|---:|---:|
| Tiny | 0.032246-0.035633 | 0.409868-0.422499 | 0.034621-0.037382 | 0.000802-0.002723 | 0.90-0.97x |
| Padded helper | 0.079110-0.088401 | 0.483273-0.502722 | 0.037783-0.040438 | 0.000980-0.002162 | 1.96-2.24x |
| Import heavy | 1.400111-1.606191 | 1.790523-1.936835 | 0.036536-0.043777 | 0.001101-0.002294 | 33.29-39.81x |
| Router, 1,000 events | 1.139759-1.356244 | 1.509427-1.623367 | 0.036402-0.040301 | 0.001152-0.002467 | 28.91-36.50x |

First fills and AOT builds are one sample per workload. The recurring miss
premium is the difference between its median and the uncached median:

| Workload | First-use fill, runtime warm | Ordinary AOT build | Recurring miss premium |
|---|---:|---:|---:|
| Tiny | 0.604393 | 0.297598 | +0.381217 |
| Padded helper | 0.723948 | 0.337140 | +0.409599 |
| Import heavy | 2.092088 | 6.345643 | +0.383186 |
| Router, 1,000 events | 1.789612 | 5.396742 | +0.418405 |

**Skipped-work control:** all 20 timed hits have exactly one `hit` event, no
frontend event, zero LLVM calls and no timeout. Every measured execution matches
CPython's output and status. The timing probe completed 328 assertions. The
prebuilt AOT launch results are a distinct control: ordinary AOT uses a different
optimization pipeline from the saved JIT-tier executable.

The old prototype and this candidate differ in validation contract,
implementation, compiler identity and measurement occasion. In particular, the
candidate checks search-layout inputs and has retention and concurrency controls.
Absolute timing differences between the two reports are not a controlled
before/after speedup measurement. Only the within-run mode comparisons above are
presented as paired speedups.

### Why the launch path changed

A diagnostic profile at source
`113485f76962d9d8f765b90eaf980f645a8666a8`, compiler SHA-256
`7a59021a752bcd4354f39d45b472eb96925d088f7d727e1dfaa593c6ab288b55`,
identified avoidable work in an earlier default-cache candidate. This was one
un-pinned diagnostic run, not a repeated or uninstrumented benchmark. Its
[retained summary](2026-11-06-program-cache-default-profile.json) records the
commands, source identities and measurement limitations.

Loader diagnostics counted 34 ELF exec transitions for one validated hit:
17 shells, ten `stat` commands, three `flock` commands, one `touch`, two compiler
images and the program. The loader-instrumented hit took 82.2 ms. `strace` was
blocked by the environment's ptrace permissions, so this is not a syscall-trace
result.

A separate native component helper, also sampled once, recorded:

| Component | One diagnostic sample |
|---|---:|
| Manifest decoding/checksum, 491,754-byte manifest | 6.40 ms |
| Complete record validation | 21.59 ms |
| Search-layout records, included in complete validation | 17.55 ms |
| Executable checksum, 504,080-byte artifact | 12.23 ms |
| One cache-directory admission check | 4.90 ms |

Per-class scans preceded complete validation and warmed those records. The
complete-validation sample includes the per-class work; those durations must not
be added together. The raw summary's single-sample medians do not establish
repeatability. Its 12.597 s preparatory fill started with runtime artifacts empty
and is outside the warm-runtime first-fill comparison above.

These observations motivated native in-process lock acquisition, consolidating
cache-directory admission checks, and streaming executable bytes through a
native FNV-1a loop. The checksum format and digest values remain unchanged.
Large static toolchain inputs use the optional `sha256sum` fast path, retaining a
bounded in-process fallback. This report makes no separate post-change component
speedup or process-count claim; the historical five-round table measures the resulting
complete launch path.

### Supported default and cache lifecycle

The default applies to the **Linux native CLI, default ORC tier and inspectable
Clang/GNU toolchain**. Unset, empty and `PYSTACHY_PROGRAM_CACHE=1` enable it;
`PYSTACHY_PROGRAM_CACHE=0` disables it. Hosted compilation, MCJIT, diagnostic
modes, custom C flags/build environments, CPython embedding and external native
libraries use ordinary compilation. `build`, `ext`, `ir`, `check` and `rt` retain
their separate behavior. See the [usage and invalidation contract](../../../docs/program-cache.md).

Source contents and positive/negative import probes are revalidated. Consumed
compiler, runtime, header, linker and loader files are hashed, with settled
metadata permitting reuse of static hashes. Existing and absent toolchain search
candidates are also checked, including header, GCC, linker, loader and Clang
configuration paths. The checked toolchain identity keys the runtime object as
well as the program, preventing a new program from using an older unchecked
runtime. Arbitrary wrappers must declare their additional inputs through
`PYSTACHY_PROGRAM_CACHE_INPUTS`; uninspectable layouts and undeclared wrappers
bypass the cache.

The cache remains private to its user. `program-v2` retains at most 256 program
contexts and 256 MiB of executables plus manifests, with a separate 8 MiB static
hash memo. Publication evicts inactive least-recently-used entries, removes
superseded executables and reclaims interrupted staging on later accesses.
In-flight staging can temporarily require additional space.

Kernel locks deduplicate simultaneous misses for the same context. The 256 lock
buckets can serialize unrelated contexts; after a 30-second wait the command
falls back to ordinary compilation. Complete artifacts precede atomic manifest
publication. A launch opens its validated executable while protected by the
lock, and the kernel closes the native lock descriptor when executing the pinned
file. Invalid or unusable entries fall back safely; the native probe explicitly
checks checksum-consistent malformed ELF and missing-interpreter failures,
preserved caller environment, no internal-marker leak and exactly-once effects.
Cross-user and remote caches are outside this contract.

### Historical validation status

The following rows record the completed local checks and their scope.
Earlier prototype CI and full-corpus results are not evidence for the current
code commit. The focused units and compiler-state controls were rerun with the
measured code commit unchanged before and after. The validation bundle retains
the logs, the explained IR differences and the initial hosted-fixture failure.
Required PR CI remains a separate gate, assessed on the final reviewed head.

| Check | Status and scope |
|---|---|
| Native compiler self-build | Passed: three-stage fixed point, 846,338 IR lines (`build-default.log`). |
| Runtime self-build | Passed: three-stage fixed point, 18,805 IR lines (`build-default.log`). |
| Focused cache units | 141 total: 140 passed, one skip, zero failures on the measured code commit. `test_program_cache*.py`: 86 passed/one skipped; `test_cached_run*.py`: 30 passed; `test_cache_toolchain.py`: 24 passed (`default-focused-units.log`). |
| Compiler-state controls | 121 passed on `e3b1b3a8d4ee810cb8215fd986f9e83526f71dba`, unchanged before/after the run (`default-focused-units.log`). |
| Default native cache probe | 498 assertions passed across all 14 requested groups; [raw evidence](2026-11-06-program-cache-default-checks.json). |
| Output-checked timing probe | 328 assertions passed; 20/20 timed hits skip frontend and LLVM; [raw evidence](2026-11-06-program-cache-default-times.json). |
| Fast lint/static checks | Passed: Ruff, mypy on 52 source files, repository hygiene, selected tool units, static GC roots, ShellCheck and C syntax checks (`default-fast-lint.log`). This is not the entire CI Lint workflow. |
| Runtime contracts | Passed: 648 runtime entries and 70 exception classes agree on signatures/coverage/effects; 172 runtime-subset functions checked (`default-runtime-contracts.log`). |
| Broad native corpus execution | Passed on the measured code/binary: 2,266 selected source cases; harness reported 2,284 passes and zero failures, JIT mode with two workers (`default-corpus.log`). `PYSTACHY_PROGRAM_CACHE` was unset and `PYSTACHY_IRCHECK` explicitly removed. This exercises eligible default compilation, not universal hit coverage. |
| IR/diagnostics/status against a pinned base | Reviewed: compared 4,238 cases with `f7103067545b43cdcd8ce20dc66b1571425b3a8d`; 4,210 had identical IR and all 59 hunks in the other 28 cases are accounted for below. All 4,238 had identical diagnostics and exit status. The original comparison exited 1 for the IR differences; that result is retained in the [validation evidence](2026-11-06-program-cache-default-validation.json). |
| Existing runtime-cache regression suite | Both halves completed: 66 native checks and 68 hosted checks passed, 134 total with zero failures in the completed runs. The hosted rerun used the corrected validation checkout; the initial failed/stopped hosted attempt is retained and described below (`default-runtime-cache.log`, `default-runtime-cache-hosted.log`). |
| Pinned CPython recordings | Passed on the measured code commit with CPython 3.13.16: 2,144 recordings, 122 deviations and 11 `lib/` files checked, zero failures. Six pinned AskMe files verified at `9256333b07628f6e4b399f41916f36d463914501` (`default-recordings.log`). |
| Relocated release smoke | Passed, exit 0: native and installed version checks without LLVM/Python; default fill/hit match CPython and hit skips frontend; normal and GC-stressed JIT/AOT match; ordinary warm JIT reuses its runtime. The relocated archive uses a Python-free PATH, read-only resources and external cache (`default-release-smoke.log`). |
| Required PR CI/full verification | Separate required gate: [PR #1103 checks](https://github.com/den-run-ai/pystachy/pull/1103/checks). Assess every applicable workflow on the final reviewed head; the PR records the actual outcome. This local evidence report does not claim a current-head CI or complete verification-matrix pass. |

The focused units and compiler-state controls total 262 tests: 261 passed, one
skipped and zero failed. The skip is the wrong-owner cache fixture: changing its
owner to UID 1 fails with `EINVAL` in this user namespace, so that ownership
scenario could not be exercised here. The skip is not counted as a pass.

#### Release smoke environment regression

The first CI attempt on `1a33fcf1b1a0f0b7d0399638adda96a799a3479e`
found a fixture mismatch in the
[Linux distribution job](https://github.com/den-run-ai/pystachy/actions/runs/42307710748/job/128204385097).
GitHub's Python setup exports `LD_LIBRARY_PATH`. The native cache correctly
bypassed that custom loader environment, and the program produced the expected
output with exit status zero, but the smoke check required a cache fill.

Commit `ca2a2828f5648a0f0f5bba23333d58d11b8a555c` changes only the release
smoke helper and its tests. Its cache-specific invocation copies the supplied
environment and removes the compiler's 19 custom build/loader inputs. The
CPython reference run, other release checks, ordinary program variables and the
caller's dictionary retain their environment. The compiler's bypass policy and
all measured compiler/runtime/library sources are unchanged.

The original smoke script was reproduced locally with inherited
`LD_LIBRARY_PATH` and failed with the same bypass trace. Under that same
condition, the corrected script passed the complete relocated release smoke:
version checks, default fill/hit, normal and GC-stressed JIT/AOT, and ordinary
warm-runtime reuse. All 50 release-related unit tests and Ruff passed. The new
subprocess regression checks the complete compiler build-environment list,
fresh ordinary values, preservation of empty values, caller immutability and
continued rejection of bypass traces. The
[validation bundle](2026-11-06-program-cache-default-validation.json) retains
the negative and corrected run logs, commands and correction identity. CI must
still pass on the final reviewed head; the earlier failed attempt is not
relabelled as successful.

#### IR comparison

The IR comparison used a common `PYSTACHY_HOME` only after verifying that all 90
library files present in the base were byte-identical in the candidate. This
avoids differences from embedded absolute checkout paths. It excluded the
compiler source `pystachy.py`, which now uses environment/private-cache helpers
unsupported by the base, and the new
`tests/programs/language/environment_mutation.py` fixture for that added API.
All 59 changed hunks in the 25 argparse-using and three wcwidth-using cases have
been reviewed in full. Each case adds one exception edge by changing
`pys_getenv` from `call` to `invoke`, reflecting its raising effect, and adds a
continuation block. The new unwind target is an existing handler in that
function. Every other difference is the induced renumbering of local labels or
SSA temporaries.

The retained checker reconstructs both sides of every complete diff hunk,
reverses only that specific call/continuation change and its local renumbering,
and requires exact text equality. It preserves every other instruction,
constant, global/string-pool identifier, operand type and instruction order.
The [validation evidence](2026-11-06-program-cache-default-validation.json)
retains the complete diff, review JSON and checker source. This accounts for all
observed IR differences; it does not turn them into byte-identical IR or provide
a general proof of semantic equivalence.

#### Runtime-cache fixture correction

The initial combined runtime-cache run completed its native half with 66 passes
and zero failures. Its hosted fixture copied `pystachy.py` and `src/` into a
temporary compiler directory but omitted `lib/_pystachy_cache.py`, now listed in
`COMPILER_SOURCES`. Missing a recorded compiler input correctly prevented
runtime-cache publication, and the harness then failed its expected-entry and
reuse checks. That hosted run was stopped; its failure output remains retained.

The test-only correction at `4a18e825a3d9e4a827fd722d8c08697cc84f7f1a` copies the
private helper beside the hosted compiler as well. ShellCheck and two harness
unit checks passed for the correction. The hosted rerun then completed with 68
passes and zero failures, giving 134 successful checks across the two completed
halves. These were separate completed runs, not one successful initial
`make test-cache` invocation. Final PR CI must run both halves. This fixture
failure and its correction do not change the measured implementation or erase
the failed attempt.

#### Execution coverage

The focused native probe covers reuse, consumed source and import invalidation,
effects and status, corruption, bypasses, tool/compiler/runtime identity,
compilation failures, deduplicated concurrent misses, signals, source races and
interruption cleanup. Normal compiler/JIT benchmark runners explicitly set
`PYSTACHY_PROGRAM_CACHE=0` so their compilation measurements keep their meaning.
The ordinary corpus harness enables the IR checker and therefore bypasses this
cache by default. The broad run recorded here explicitly removed that flag at
the compiler boundary and left the cache setting unset. Eligible programs thus
used the default path; the run does not establish that every case produced a
cache hit or cover the other modes in full verification.

### Reproduce the historical candidate

Use a clean checkout at the measured code commit and the supported development
environment from [installation](../../../docs/install.md). The following uses a
standard LLVM installation path; the raw reports retain this host's exact paths.
Use CPython 3.13.16 and LLVM 18.1.3 to match the recorded versions, and record the
resulting compiler hash and host details for a new run.

```sh
git checkout e3b1b3a8d4ee810cb8215fd986f9e83526f71dba
export PY=python3.13
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin

make pystachy PY="$PY"
sha256sum ./pystachy

"$PY" tools/program_cache_probe.py \
  --compiler ./pystachy --python "$PY" --llvm "$PYSTACHY_LLVM" \
  --output build/program-cache-default-checks.json

"$PY" tools/program_cache_probe.py \
  --compiler ./pystachy --python "$PY" --llvm "$PYSTACHY_LLVM" \
  --benchmark-only --rounds 5 --cpu 0 \
  --output build/program-cache-default-times.json
```

Run correctness checks before timing, with no intentional concurrent bootstrap
or other heavy workload. Choose an allowed CPU if CPU 0 is unavailable and retain
that change in the new report. The probe clears inherited compiler/build
settings, leaves the cache enable setting unset, creates its own private cache
and tool wrappers, warms both runtime lineages, and applies the cache cleanup
boundaries above. Do not remove runtime artifacts between its samples. Require
`completed: true`, `passed: true` and no setup error before using the timings.

The recorded broad default-mode corpus run is reproduced with:

```sh
PYSTACHY_JOBS=2 tests/run.sh \
  "env -u PYSTACHY_IRCHECK -u PYSTACHY_PROGRAM_CACHE $(pwd)/pystachy" \
  jit tests/programs/*/*.py tests/deviations/*.py
```

For the focused units and existing cache/contract checks, use the corrected
validation checkout. Its only change from the measured code is the hosted cache
fixture described above:

```sh
git checkout 4a18e825a3d9e4a827fd722d8c08697cc84f7f1a
"$PY" -m unittest discover -s tools -p 'test_program_cache*.py'
"$PY" -m unittest discover -s tools -p 'test_cached_run*.py'
"$PY" -m unittest discover -s tools -p test_cache_toolchain.py
"$PY" -m unittest discover -s tools -p 'test_compiler_state*.py'
make test-cache PY="$PY"
make check-fast check-runtime PY="$PY"
make check-recordings PY="$PY"
```

These completed local checks complement the repository's complete
[verification gates](../../../docs/testing.md#continuous-integration), which
remain required on the final reviewed PR head for merge/release readiness.
