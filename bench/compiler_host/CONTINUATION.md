# Continuing compiler optimization: memory, inlining and imported partitions

Research continuation of [PR #1091](https://github.com/den-run-ai/pystachy/pull/1091),
Linux x86-64, 2026-11-06 UTC. The prior [bootstrap study](OPTIMIZATIONS.md) remains
a separate cohort. Ordinary whole-module O2 remains the final-backend default.

## Results and decisions

| Change | New evidence | Decision |
|---|---|---|
| Compact LLVM output construction | Self peak RSS 905.7 → 840.1 MiB, 7.2% less; corroborated in three cohorts | Retain both changes on the draft branch; execution cost remains unresolved |
| Optional LLVM inlining threshold | Frozen backend O2 69.89 s, threshold 75 51.64 s; one build each | Explicit opt-in; complete-bootstrap results below |
| Import functions across LLVM partitions | Complete bootstrap 134.18 → 94.30 s, 29.7% less; resulting self frontend median 2.6% higher | Bounded opt-in self-build profile; more CPU and larger executable |
| Offline instrumentation PGO | Strict profile-use build 72.41 s plus 92.03 s preparation/training; self median 5.476 vs 5.799 s in one five-sample cohort | Keep exploratory; no bootstrap acceleration established |

The integrated compiler source is frozen at
`9b75dd6288e00a8290f3cb6b8190b8740ed54070`. Results below distinguish this
source from the earlier `fa9bba37` inputs and separately prepared memory candidates.

### Repeated complete bootstraps

[Nine complete bootstraps](results/continuation-bootstrap.json) use three rotated
interleaved rounds, the same frozen source, fresh runtime caches and CPU affinity
0–3. Every run includes two actual native compiler builds, three compiler IR
witnesses and three runtime IR witnesses. All **54 witnesses match**, all nine
temporary compilers are byte-identical, and final executable bytes repeat exactly
within each policy. Different final policies intentionally produce different
machine code; this is not a claim of cross-policy executable parity.

| Complete bootstrap policy | Median wall, s (range) | Total CPU-s | Sampled aggregate peak RSS, MiB | Final executable bytes |
|---|---:|---:|---:|---:|
| Ordinary O0 temporary → ordinary O2 final | 134.18 (132.61–136.91) | 135.31 | 920.5 | 5,243,088 |
| Ordinary O0 temporary → O2 threshold75 final | 117.52 (114.11–117.98) | 118.55 | 920.6 | 4,107,232 |
| Ordinary O0 temporary → ThinLTO4 final, runtime overlap | 94.30 (90.71–97.59) | 157.44 | 938.5 | 6,187,432 |

Threshold75 uses **12.4% less wall time and CPU** in this complete-build cohort.
ThinLTO uses **29.7% less wall time**, with **16.4% more CPU**, **2.0% more sampled
aggregate RSS** and an **18.0% larger executable**. The median second-build time
falls from 83.05 to 43.49 s. The ThinLTO policy includes four build slots and
runtime overlap; its difference is not an isolated parallel-scheduling speedup.
The earlier 40.3% early-split bootstrap result remains a different source/cohort
with a different generated-compiler tradeoff. These new results do not supersede
it with a direct ranking.

### Execution quality of the integrated compilers

[Five interleaved fresh processes per host and workload](results/continuation-final-quality.json)
compare the actual first final executable from each bootstrap policy, the frozen
`fa9bba37` ordinary native baseline, and the reused compatible mypyc host. They
process the same five frozen inputs: self, JSON repair, runtime, unchanged mypyc
NameGenerator, and pidigits. **125/125 emitted outputs match**; all 48 mypyc
compiler modules load as compiled extensions. Host preparation and LLVM native
backend work are excluded.

| Compiler host | Self median, s (range) | Self peak RSS, MiB | JSON repair, s | Runtime frontend, s |
|---|---:|---:|---:|---:|
| Ordinary native, frozen `fa9bba37` | 6.049 (5.377–6.663) | 905.6 | 0.240 | 0.068 |
| Current native, ordinary O2 | 5.722 (5.475–6.053) | 871.1 | 0.241 | 0.064 |
| Current native, threshold75 | 5.995 (5.666–6.456) | 839.2 | 0.229 | 0.066 |
| Current native, ThinLTO4 | 5.870 (5.758–6.178) | 842.5 | 0.250 | 0.069 |
| Compatible typed mypyc, GCC O2 | 7.764 (7.152–7.808) | 645.7 | 0.422 | 0.141 |

Relative to current ordinary O2, the threshold75 self median is **4.8% higher**
and ThinLTO is **2.6% higher**. In paired rounds, threshold75 is slower in four
of five (median change +6.65%), and ThinLTO in all five (median +2.59%, range
+0.16% to +9.45%). All native ranges overlap; this is a measured tradeoff in a
small cohort, not a proven broad application penalty or runtime equivalence.
Ordinary O2 remains the default. Current ordinary native is **1.36x
the reused typed mypyc host** on this frontend workload, with **34.9% more RSS**.
The host source preparations differ: current native includes the output changes;
mypyc uses the earlier compatible overlay. Applying the output changes to mypyc
was not measured.

Integrated ordinary O2 saves **3.8% RSS** versus the same-cohort frozen baseline,
less than the isolated memory candidate's repeatable 7.2%. All three current
backend policies compile identical raw compiler IR, but have different frontend
RSS. This is evidence that the saving depends on generated code. Conservative
root retention and collection timing are possible causes; these runs have no GC
or peak-phase instrumentation that identifies the cause. Do not extrapolate the
isolated 7.2% saving to every backend. The lower current ordinary time also does
not resolve the isolated memory candidate's mixed timing evidence below.

## What changed in the compiler

The output changes preserve every LLVM byte. Module assembly now includes its
final newline in the join rather than making a second module-sized string. Each
completed function and its adjacent coroutine/recursion/tuple-return wrappers is
retained as one string; its individual line strings are released before the next
function is lowered. The output list retains its identity and order. Module
declarations, dispatch definitions and metadata retain their original order.
There is no change to GC policy, object layout, inference, or the compilation
algorithm. Existing native join-of-slice lowering avoids an extra list copy.

The optional `PYSTACHY_AOT_INLINE_THRESHOLD=75` setting changes only native
`build` optimization. Unset or empty uses LLVM's existing policy; `0..10000` is
accepted and invalid values fail before the frontend. JIT and extension settings
are unchanged. The bootstrap has separate stage1/stage2 threshold controls;
isolated worker job version 2 binds the setting to the job/result. Version 1 jobs
remain replayable only without a new policy field. The allocator late-inline
contract is preserved. Tests cover both allocation and non-allocation routes.

## Controlled memory experiment

[Raw memory samples](results/continuation-memory-quality.json) compare ordinary
O2, the final-newline change alone, and both output changes. All use ordinary O2
backend preparation and compile the same frozen `fa9bba37` inputs. Each native
candidate reproduced its own retained build IR, frozen compiler IR and runtime
IR. Five randomized interleaved fresh processes per host/input use CPU 0, timing
and GC statistics. Preparation is excluded.

| Native host | Self median, s | Range, s | Median process peak RSS, MiB | GC heap peak, MiB | Live at last GC, MiB |
|---|---:|---:|---:|---:|---:|
| Ordinary | 6.245 | 5.975–6.533 | 905.7 | 909.8 | 316.0 |
| Final-newline change | 6.290 | 6.126–6.477 | 875.6 | 879.7 | 316.0 |
| Both output changes | 6.229 | 6.007–6.444 | 840.1 | 837.2 | 309.2 |

All three made 13 collections. Avoiding the final copy saves about 30.1 MiB RSS;
both changes save 65.6 MiB. Runtime-accounted heap peak, last-GC live bytes and process RSS
are different quantities; this does not measure peak live AST/IR size. The stable
RSS improvement is the demonstrated result. The separate seven-host cohort below
has a higher compact-output median, with overlapping ranges. Neither study
establishes a consistent execution-speed change. GC time also did not improve:
the respective medians are 931.4, 934.2 and 939.6 ms.

A prespecified replay used nine interleaved rounds, the same three executables
and frozen self input, CPU 0 and timing enabled, with GC statistics disabled.
[All 27 outputs matched](results/continuation-memory-replay.json).

| Native host | Self median, s | Range, s | Process peak RSS, MiB |
|---|---:|---:|---:|
| Ordinary | 6.086 | 5.349–6.417 | 905.7 |
| Final-newline change | 5.971 | 5.723–6.747 | 875.6 |
| Both output changes | 6.054 | 5.571–6.673 | 840.2 |

For both changes versus ordinary, the ratio of host medians is 0.52% lower, while
the median within-round ratio is **2.71% higher**, with six of nine rounds slower.
Individual paired changes range from −10.39% to +8.23%. The earlier isolated and
seven-host cohorts have host-median changes of −0.27% and +7.65%, respectively.
The replay does not reproduce a stable 7.65% loss, but neither overlapping ranges
nor the lower overall median establish equivalence or exclude a material cost.
The repeatable result is memory reduction; this is not a claim of a cost-free
production default. No further timing replay was selected to improve that result.

## Same-input native and mypyc comparison

[Raw seven-host comparison](results/continuation-policy-quality.json): five
interleaved fresh-process samples for each of five workloads, **175/175 exact
outputs**, plus five ordinary-native oracle processes. All 48 mypyc compiler
modules loaded from their intended compiled extensions. The prepared compatible
typed-mypyc host is reused from the prior study; hashes and import origins are
checked before and after. This is a frontend comparison, excluding host
preparation and LLVM optimization/code generation.

| Compiler host | Self median, s (range) | JSON repair, s | Runtime frontend, s | NameGenerator, s | Pidigits frontend, s | Self peak RSS, MiB |
|---|---:|---:|---:|---:|---:|---:|
| Ordinary native O2 | 5.799 (5.762–6.497) | 0.277 | 0.069 | 0.0082 | 0.0415 | 905.7 |
| Native, threshold 75 | 6.300 (5.822–6.618) | 0.268 | 0.075 | 0.0086 | 0.0416 | 904.9 |
| Native, compact output | 6.242 (5.721–6.406) | 0.289 | 0.070 | 0.0087 | 0.0434 | 840.1 |
| Native, ThinLTO4 importing | 5.903 (5.554–6.263) | 0.301 | 0.071 | 0.0089 | 0.0442 | 908.0 |
| Native, PGO + threshold75/hot300 | 5.476 (5.061–5.985) | 0.257 | 0.057 | 0.0078 | 0.0347 | 916.1 |
| Native, existing early split4 | 6.270 (5.458–6.599) | 0.315 | 0.079 | 0.0096 | 0.0460 | 906.8 |
| Compatible typed mypyc, GCC O2 | 7.582 (7.196–7.640) | 0.467 | 0.148 | 0.0462 | 0.0942 | 645.7 |

On this cohort ordinary native is 1.31x typed mypyc on the self frontend, with
40.3% higher process peak RSS. Compact output remains about 30.1% above mypyc RSS.
These percentages belong to this cohort, not the earlier 5.811/7.354-second study.
The compact native host includes the output changes, while the reused mypyc host
has the earlier source plus its compatible typing overlay. The smaller observed
RSS gap does not measure what the same output changes would do to mypyc.
Self RSS uses wait4 process high-water values; the sampler misses part of mypyc's short peak. Short-process sampled RSS can miss almost the entire process: the sub-MiB
NameGenerator samples are not useful memory rankings. Shared pages and the
sampling interval also limit process-tree RSS. No hardware-independent speed
ranking or full-mypyc/mypy reverse-direction compatibility is implied.

The self and JSON inputs trained PGO. Runtime, NameGenerator and pidigits are
held out, but the latter are small frontend compilations, not a broad application
execution suite. Overlapping ranges and shared-host variability limit the
strength of small runtime differences. The lower PGO median is a lead, not a
default-policy decision.

## LLVM growth, inlining and profile guidance

[Frozen backend screen](results/continuation-inline-screen.json), one build per
policy from the exact same linked compiler/runtime bitcode:

| Policy | Backend wall, s | CPU-s | Peak RSS, MiB | Approx. optimized instructions | Executable bytes |
|---|---:|---:|---:|---:|---:|
| Ordinary O2 | 69.89 | 69.87 | 536.1 | 886,072 | 5,242,824 |
| Threshold75 | 51.64 | 51.60 | 407.4 | 563,112 | 4,106,968 |
| Threshold125 | 59.63 | 59.61 | 456.8 | 723,393 | 4,532,336 |

Threshold75 reduces approximate optimized instructions by 36.4% and executable
size by 21.7%. The build observations are exploratory, with no repetitions. The
ordinary compiler is byte-identical to the previous reviewed ordinary executable.
All six build witnesses and fifteen interleaved self-execution outputs match.
This explicit screen retains its late-allocator pass even when that pass is a
no-op; the production driver can bypass it. It also writes report checkpoints
within the backend interval. The PGO harness excludes those writes from its
backend interval. Use stage-command sums for a strict comparison between those
two harnesses; the complete-bootstrap study measures the actual selected driver.
Complete-bootstrap measurements provide the separate repeated end-to-end test.

PGO uses LLVM IR instrumentation, merges profiles, then rebuilds the same input.
The strict run separately measures 81.82 s instrumented preparation, 9.70 s self
training, 0.48 s JSON training and 0.023 s merging before its 72.41 s optimized
backend. It produces 742,130 approximate instructions and a 4,935,760-byte
compiler. This is not a build-time win; training needs amortization and future
input changes need revalidation. Reuse requires the original completed training
report, identical input/source/tool/profile bytes and a private verified copy.

An initial PGO screen used Clang's frontend profile warning groups, which do not
enforce LLVM IR profile compatibility. Its evidence is retained separately.
Negative controls found that IR mismatches use `backend-plugin`, and missing
function profiles require an explicit warning flag. The corrected harness treats
these diagnostics as errors, including weak/COMDAT mismatches; an actual
structural mismatch is rejected. Actual tool binaries and profile runtime
archives are identified, in addition to the wrapper manifest. Profiles are not
trusted solely because an optimizer exits successfully.

## Partition quality and limits

ThinLTO prepares compact module summaries, performs an index step and imports
selected function bodies before independently optimizing partitions. The
[LLVM18 documentation](https://releases.llvm.org/18.1.8/tools/clang/docs/ThinLTO.html)
describes this boundary. The prototype uses `llvm-lto2` because LLD is unavailable
in this local toolchain, followed by the ordinary native link. It is explicitly a
Linux x86-64 compiler-self-build experiment, not a general linker replacement.

The frozen four-partition/four-worker screen took **28.05 s**, **85.45 CPU-s** and
**693.2 MiB sampled aggregate peak RSS**. Timing includes preflight, splitting,
summary construction, symbol resolution, optimization/codegen, native linking
and retained import/optimized bitcode. It excludes later disassembly inspection
and compiler execution. The LTO stage took 20.94 s; splitting took 3.65 s.
The executable is 6,182,928 bytes, about 17.9% larger than ordinary O2. This is one
build and is not an isolated scheduling-speedup measurement.

The input has 3,672 function definitions. Importing adds 3,464 available-externally
body copies across the partitions. That recovers optimization visibility but
duplicates work and helps explain higher CPU demand; it does not prove the exact
cause of each performance difference. Complete-bootstrap results must include
the controller and overlapping work, not sums of overlapping stage wall times.

The first preflight rejected two empty inline-assembly pointer barriers from
the runtime. The corrected allowlist accepts only their exact empty template and
register constraint, preserving the instruction and explicit LLVM operand.
Nonempty/module assembly, unsupported symbol classes and actual allocator
symbols still fail closed. Tests exercise native indirect calls through the
barrier, weak/strong selection, deterministic worker-count outputs, corrupted
compiler/runtime witnesses and altered harness identity. Job version 2 binds the
Python executable and imported harness files as well as input/settings/tool
hashes. The first screen predates that extra dependency gate and is labeled so.

`self_pipeline.py --backend thinlto` provides the bounded O2 path. The measured
complete-bootstrap policy combines `--stage2-thinlto 4` with `--stage1-opt 0`,
retaining an ordinary O0 temporary compiler and all six compiler/runtime
witnesses. Final-stage splitting,
full-LTO codegen partitions and a final inlining override cannot be combined
with this path. Source, producer, submitted job, tools, harness and final
executable are checked before publication; the coordinator retains the original
job digest, so changing both a job and its returned digest is rejected.

The complete policy also uses four build slots and whole-runtime overlap. That
changes stage1 slot reservation and whether its first runtime witness can overlap
the build. Its timing difference is a **combined policy result**, even though
the temporary executable bytes must remain identical. It is not an isolated
parallel-scheduling speedup. The standalone screen separately reports backend work.

ThinLTO's backend threads run inside a local LLVM process. This path does not yet
provide a portable remote job for each imported partition. The existing separate
early-split workers retain their standalone replay contract; distributing the
importing path will also need per-partition index/import dependencies.

## Reproduce the experiments

Use CPython 3.13.16, LLVM 18.1.3 and new output directories. The committed JSON
retains the exact original argv and paths; replace checkout, toolchain and output
roots when replaying elsewhere. It does not promise byte-identical native files
across different system linkers or sysroots.

For the complete integrated cohort, create a clean worktree at `9b75dd62`, then
run the following from the research checkout. `$benchmark_llvm` is the matching
LLVM executable directory and `$benchmark_root` is that frozen source worktree:

```sh
python3.13 bench/compiler_host/bootstrap_followup.py \
  --root "$benchmark_root" --llvm "$benchmark_llvm" \
  --work /tmp/pystachy-bootstrap-study --report /tmp/pystachy-bootstrap-study.json \
  --variant driver-o0 --variant driver-inline75 --variant driver-thinlto4 \
  --samples 3 --cpus 0-3
```

Every run makes two actual native compilers; all three compiler and three runtime
witnesses remain mandatory. For only the explicit ThinLTO profile, use
`python3.13 tools/bootstrap_pipeline.py --variant optimized --runtime-c-cache --timing
--jobs 4 --build-jobs 4 --stage1-opt 0 --stage2-thinlto 4 --runtime-overlap`, with
the same `--root`, `--llvm` and a new `--output` directory.

The standalone `optimization_tiers.py`, `profile_guided.py` and
`partition_import.py` consume one frozen snapshot containing `linked.bc`,
`raw.ll` and `seed-rt.ll`. `self_pipeline.py` can create those artifacts from a
verified compiler and a frozen source worktree. The
[provenance record](results/continuation-provenance.json) identifies this study's
exact copied snapshot, source commits, native hosts and unchanged upstream
NameGenerator input. Preparation is outside frontend timings.
The frontend harness's `source` field fingerprints its own checkout, not the
complete `PYSTACHY_HOME` tree. The separate frozen-input manifest and independent
rehashes supplement that evidence; they do not retrofit a full-tree before/after
guard into each timed frontend run.

The memory hosts are ordinary O2 builds of `f4826b4e` and `a87b5c89`, using the
ordinary frozen native compiler as producer. Their exact native preparation argv
and witnesses are in [the preparation record](results/continuation-memory-builds.json).
`output_memory.py --root CANDIDATE --output NEW_DIRECTORY` reproduces the focused
hosted byte comparisons on either candidate worktree. `run.py` takes the supplied
[memory config](results/continuation-memory-quality-config.json),
[replay config](results/continuation-memory-replay-config.json), or
[seven-host config](results/continuation-policy-quality-config.json), plus new
`--work`, `--report`, `--samples` and `--cpu 0` arguments. Edit only the local
paths in a copied config; keep each cohort's samples and instrumentation separate.
The [integrated quality config](results/continuation-final-quality-config.json)
uses each first repeated bootstrap's final executable and the same five frozen
inputs, with `--samples 5 --cpu 0`. It does not use the integrated compiler's
newer source as the frontend input.

## Validation and remaining work

Completed before the integrated bootstrap cohort:

- 20 focused hosted IR/diagnostic/status comparisons for each memory candidate;
  six post-build native witnesses across the two prepared memory candidates.
- 45 isolated memory, 175 seven-host and 27 replay outputs: **247/247 exact**.
- **4,238/4,238** corpus comparisons for the compact native compiler against the
  frozen ordinary compiler, including IR, diagnostics and exit status.
- **13/13 compiler-heap GC checks**: exact self IR with collection every 5,000
  allocations, then six lowering fixtures under both default and disabled
  optimizations with collection every allocation. These stress the compiler,
  not only emitted programs. The self check completed in 436.43 s within its 600 s
  bound; it is a correctness run, not a comparative performance benchmark.
- Fast checks and lint: 449 tests, four optional LLVM/cache checks skipped in
  the default run. Worker/experiment controls: 90 tests, five optional LLVM
  checks skipped in that invocation. Focused real-LLVM checks are separately
  recorded; counts overlap and must not be added as unique tests.

Integrated source and resulting compilers also passed:

- Nine complete bootstraps, **18 native builds and 54 exact IR witnesses**;
  executable bytes repeat within each policy and all temporary compilers match.
- **125/125** additional controlled frontend outputs, bringing the four main
  execution cohorts above to **372/372** exact outputs.
- [**4,238/4,238 corpus comparisons each**](results/continuation-integrated-corpus.json)
  for the integrated ordinary and ThinLTO compilers against the frozen baseline.
  The shared library/runtime home is justified by another 96-file identity check.
- [Native IR/runtime checks](results/continuation-native-validation.json): all
  **2,358 accepted corpus programs** pass the typed-IR checker and `llvm-as`;
  all 644 runtime entries agree with their signatures, coverage and effects.
- Six focused lowering fixtures pass JIT and AOT normally and with program
  collection on every allocation: **24 execution comparisons**. The ThinLTO
  compiler itself also emits exact oracle IR for all six fixtures under default
  and disabled optimizations with collection on every allocation: **12 checks**.
  A real native extension is built and imported; scalar, tuple-return and string
  exception paths pass under normal and per-allocation collection.
- Real native default/empty/0/75 inlining and runtime reuse, allocator object
  parity, C-runtime cache invalidation/publication, and **90/90 LLVM-enabled
  worker/partition/profile controls** pass. Default and empty inlining settings
  produce identical executables; runtime cache hashes, inodes and mtimes remain
  unchanged when only the inlining policy changes.

- Full unchanged runtime-cache suites pass **134 assertions: 66 native and 68
  hosted**, including invalidation, interrupted-build publication and recovery.
  No process-discovery helper or test-assertion substitution was used.

The [validation index](results/continuation-validation.json) records exact
commands, source/executable checks, linked logs and evidence hashes. Validation
ran in separately bounded groups after all timing cohorts finished. The PR's
checks record CI on the published head; old-head CI is not claimed for these
new changes.

The full local `make verify`, macOS execution, and actual cross-host work were
not run for this continuation. The existing full-LTO driver-tier integration
method additionally needs the locally unavailable `ld.lld`; it was not invoked.
The new ThinLTO tests use `llvm-lto2` and passed with real LLVM. These local checks
are not a claim of a complete verification matrix. The PR remains draft.

The initial corpus run used different worktree library paths and reported 261
differences, with import-error path literals embedded in IR. The corrected run
used one frozen library path only after verifying all 96 runtime/library source
files were byte-identical. It still required exact emitted IR; no string-literal
normalization was added. [Both attempts and the identity proof are retained](results/continuation-memory-corpus.json).
The initial ThinLTO preflight rejection and the insufficient initial PGO warning
gate are retained separately. A unit-control run also exposed an incorrect test
helper keyword, which was corrected before its 31-test rerun passed.

All experiments use pinned CPython3.13.16 and LLVM18.1.3 on the same AMD EPYC9V74
container (eight CPUs quota, 8GiB memory cap). Timing runs are serial with respect
to other full local builds; frontend measurements use CPU0 and builds CPU0–3.
This is a shared container, not reserved hardware. Exact argv, identities,
sample ranges and failures are in the raw JSON. The frozen input source is
`fa9bba371c792999b6161b8aa507e8c584b1b0f5`; NameGenerator retains the original
upstream file/hash recorded in the preceding report.

The work remains local. Transport, retry/idempotent shared-cache publication,
complete target/sysroot/shared-library identity, stable incremental partitions,
and a fleet-wide CPU plus memory budget remain distribution blockers. More
workers do not eliminate the split/index work or duplicated imports. The mypyc
comparison still points to loading/inference and memory retention as useful
targets; native Pystachy already specializes the receiver calls, so adding the
same annotations is not another demonstrated native optimization. General
native mypy/mypyc compilation remains component-level.
