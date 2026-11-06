# Native program cache: complete-launch prototype, 2026-11-06

This experiment addresses [#104](https://github.com/den-run-ai/pystachy/issues/104):
reuse a native program across unchanged `pystachy run` launches. A valid hit
checks its inputs and executes the saved program in a fresh process, skipping
the compiler frontend and LLVM. It does not cache program output or module
initialization effects. The implementation is opt-in and Linux/native-CLI only.

**Measured result:** validated hits reduced the import-heavy launch from a
1.616 s median to 0.0337 s and the complete 1,000-event router command from
1.267 s to 0.0300 s. Their median paired speedups were 50.30x and 40.93x;
the tiny and padded-helper probes improved 1.59x and 3.26x. Every timed hit
skipped the frontend and all five LLVM tools.

The costs remain material: recurring program misses were 0.159-0.176 s slower
than uncached launches by difference of medians. A first fill with empty program
metadata and a warm runtime took 4.585-6.160 s, including initial toolchain
hashing. That metadata is shared by subsequent programs. These launch results
do not establish a long-running application or release-wide runtime speedup.

## Pinned inputs and host

| Item | Value |
|---|---|
| Base | `f7103067545b43cdcd8ce20dc66b1571425b3a8d` |
| Published implementation and harness | `37fb87fbd1034de785dc26917bb151a8dafc2d61` |
| Locally tested source commit | `6a15d6e1386547cd8eaaae182bb15db4fd3f2fea` |
| Identical implementation tree | `8b3d7c2b13831c7c7ba00c3c0392b17e7110dba4` |
| Measured native compiler SHA-256 | `df000379236b3b920463c1c1960e4a73bef5672aeefb46bb580664b944d3643b` |
| CPU | AMD EPYC 9V74 80-Core Processor; measurements pinned to CPU 0 |
| Container CPU quota | `cpu.max = 800000 100000` (eight CPUs of quota) |
| Container memory limit | `8589934592` bytes (8 GiB) |
| Platform | Linux 6.18.57, x86-64, glibc 2.39 |
| Hosted Python | CPython 3.13.16 |
| LLVM | 18.1.3, Ubuntu `18.1.3-1ubuntu1`, matching five tools |
| Repetitions | Five interleaved rounds per workload; one separate first-use fill |
| Raw timing evidence | [2026-11-06-program-cache-times.json](2026-11-06-program-cache-times.json) |
| Raw correctness evidence | [2026-11-06-program-cache-checks.json](2026-11-06-program-cache-checks.json) |

The CPU model names the host processor, not the container's available CPU
allocation. The benchmark and all its child processes inherit the single-CPU
affinity. The source commit and executable hash identify different inputs: the
source being reviewed and the compiler that was actually measured. Publication
through the GitHub app created a new commit identity; its tree was verified to
match the locally tested source tree exactly. No implementation files changed.

## What is compared

The [probe](../../../tools/program_cache_probe.py) measures complete fresh
launches: process startup, cache validation, compilation when required, and
program execution. It first checks each workload against CPython, warms the
runtime cache with an ordinary cache-disabled run, and builds its AOT control.

| Mode | Cache state and included work |
|---|---|
| Uncached run | Program cache disabled; runtime artifacts warm. Frontend, LLVM and execution are included. |
| Recurring program miss | Program manifests, executables and staging directories removed; `static-hashes` and runtime artifacts retained. Includes validation, compilation, linking, publication and execution. |
| Cache hit | Fresh process immediately after a checked miss. Includes input validation and execution. Each sample must show a hit, omit the frontend trace, and invoke zero wrapped LLVM tools. |
| Prebuilt AOT | Fresh launch of an executable from ordinary `pystachy build`. Its build cost is excluded here and reported separately below. |
| First-use fill | One separate sample with the entire `program-v1` subtree empty and the runtime cache warm. Includes the initial static/toolchain identity hashing. |

The recurring miss is not a completely empty cache. The first-use fill is not a
cold runtime or a cold operating-system page cache. No page-cache flush is
performed. These distinctions matter because initial hashing can cost more
than later misses and must not be hidden in a steady-state median.

Within each round, the order is uncached run, miss/hit pair, then AOT; alternate
rounds reverse the two outer controls. The miss and hit stay adjacent so every
timed hit has a known, output-checked producer. Table values are medians of five
wall-time samples. The paired hit speedup is the median of the five ratios
`uncached[i] / hit[i]`, not the ratio of the two reported medians.

All modes must match exit status, stdout and ordinary stderr. Only the cache's
diagnostic trace is removed from stderr for comparison. Transparent wrappers
count calls to `clang`, `opt`, `lli`, `llvm-link` and `llvm-as`; their real tools
and loaded libraries are declared as identity inputs. Trace and wrapper
instrumentation remain enabled during measurement, so these are measurements
of the instrumented probe path. Wrapper overhead is included when a mode
invokes a tool.

## Workloads and results

| Workload | Exact scope |
|---|---|
| Tiny | `print(1)`; primarily startup and compilation overhead. |
| Padded helper | 600 annotated helper definitions; one live call, `helper_599(4)`. |
| Import heavy | Imports and uses `re`, `textwrap`, `json` and `fnmatch` with small deterministic inputs. |
| Router | Existing `examples/route/route.py`, 1,000 events, three rules, four event names, `--names`, ordinary streaming path. |

The JSON records the generated source text and its hashes, command arguments,
observed outputs, per-run tool counts, statuses and raw timing samples. The
router is a repository application workflow; the other three are deliberately
small compilation/startup probes.

All times below are seconds. No timing threshold is used as a correctness gate.

| Workload | Uncached run | Recurring program miss | Cache hit | Prebuilt AOT | Paired hit speedup |
|---|---:|---:|---:|---:|---:|
| Tiny | 0.035131 | 0.211120 | 0.022137 | 0.002089 | 1.59x |
| Padded helper | 0.070913 | 0.229700 | 0.021768 | 0.001957 | 3.26x |
| Import heavy | 1.616038 | 1.791227 | 0.033716 | 0.002436 | 50.30x |
| Router, 1,000 events | 1.267457 | 1.429396 | 0.029960 | 0.002523 | 40.93x |

Observed minimum-maximum ranges of the five samples, in seconds:

| Workload | Uncached run | Recurring program miss | Cache hit | Prebuilt AOT |
|---|---:|---:|---:|---:|
| Tiny | 0.032326-0.040017 | 0.189368-0.213187 | 0.020819-0.024671 | 0.000841-0.002376 |
| Padded helper | 0.067736-0.074404 | 0.218692-0.232845 | 0.021158-0.024585 | 0.000808-0.002005 |
| Import heavy | 1.535184-1.766530 | 1.708174-2.042040 | 0.030518-0.041612 | 0.001434-0.002600 |
| Router, 1,000 events | 1.185090-1.404946 | 1.360393-1.653284 | 0.028981-0.037293 | 0.001259-0.002868 |

These one-off costs are reported separately from the five-round medians:

| Workload | First-use fill, runtime warm | Ordinary AOT build |
|---|---:|---:|
| Tiny | 4.735255 | 0.306556 |
| Padded helper | 4.585234 | 0.335672 |
| Import heavy | 6.160133 | 6.383927 |
| Router, 1,000 events | 5.946480 | 5.435300 |

**Skipped-work control:** all 20 timed hits had exactly one `hit` trace, no
frontend entry and zero LLVM tool calls. The benchmark completed all 316
assertions, with `completed: true`, `passed: true`, and no setup error. All
first-fill, recurring-miss, uncached and AOT outputs/statuses also matched
CPython. The prebuilt AOT controls were much faster to launch than the validated
cache hits; the remaining 22-34 ms hit overhead includes compiler startup,
source/input validation and executable checksumming.

## Correctness and unchanged defaults

| Check | Recorded result |
|---|---|
| Native self-host compiler IR | Three-stage fixed point, 839,506 lines |
| Native self-host runtime IR | Three-stage fixed point, 18,805 lines |
| Cache disabled versus pinned base | 4,238 corpus cases with identical IR, diagnostics and status |
| Cache/storage/dependency-parser units | 54 passed |
| Native program-cache probe | 458 assertions passed across all 14 requested groups |
| Existing runtime-cache suite, native | 66 passed |
| Existing runtime-cache suite, hosted | 68 passed (134 native + hosted checks total) |
| Static checks | Full `make lint` and runtime contract checker passed; mypy checked 51 source files |
| Compiler-state ownership and restart controls | 121 passed after the CI integration correction below |
| Pinned CPython recordings | 2,142 recordings, 122 deviations and 11 library files checked; zero failures |
| Local full verification matrix | Not run; the PR CI matrix is a separate gate from the local evidence here |

The native probe covers reuse, source and import invalidation, runtime effects,
corruption, bypasses, tool/compiler/runtime identities, failures, concurrent
misses, signals, a source race, and interrupted code generation. Invalidation
includes same-size edits with restored mtimes, new shadowing imports and an
optional import that appears later. Runtime checks vary arguments, stdin and
environment and exercise initialization, exceptions, callbacks, GC stress and
the runtime-input float-power regression. Fault injection is confined to
private temporary copies and caches.

[Validation metadata and retained logs](2026-11-06-program-cache-validation.json) record the
host, source identities, successful build, IR comparison, runtime-cache checks
and lint output. The base compiler was built in an isolated worktree. Both
compilers used the candidate home for the IR comparison only after confirming
that `lib/`, `runtime.c`, `runtime.py`, `ryu/` and `mpz/` were byte-identical to the
pinned base. No compiler/runtime sources changed after the measured binary's
successful fixed-point build.

The unchanged-default corpus result establishes that leaving the option unset
preserves the checked compiler outputs; it is not a claim that every corpus
program was executed through a cache hit. The enabled-cache execution evidence
is the focused native suite and the output-checked benchmark workloads.

### CI integration correction

The [initial Lint attempt](https://github.com/den-run-ai/pystachy/actions/runs/42281206336/job/128110320421)
at PR head `a5d637dba744f4f1064fab37d81cdd7d6ceca1ca` failed 11 of 121
compiler-state controls: the new cache globals had not been registered in the
ownership inventory, producing 22 diagnostics. The follow-up classifies two
read-only tables and seven retained cache-state containers, registers their 13
observed direct writers, and documents the attempt/retry lifecycle. The checker
and its negative controls are unchanged.

All 121 compiler-state controls then passed locally in 105.388 s. The pinned
CPython recording check also passed with the counts above. This correction
changes only the ownership inventory, its documentation and this validation
record; the measured compiler, cache and benchmark sources are unchanged. PR
CI remains a separately reported gate on the current head.

## Reproduce

Use a clean checkout at the implementation commit above. These paths record the
Python and LLVM installations used on this host; adjust only installation roots
on another machine, and retain the versions and resulting executable identity
in that run's report.

```sh
cd /workspace/scratch/e98dc1e3e6cd/pystachy
export PY=/workspace/scratch/e98dc1e3e6cd/dev/bin/python
export PYSTACHY_LLVM=/workspace/scratch/e98dc1e3e6cd/toolchains/ubuntu-18.1.3-1ubuntu1-amd64/bin

make pystachy PY="$PY"
sha256sum ./pystachy

"$PY" tools/program_cache_probe.py \
  --compiler ./pystachy --python "$PY" --llvm "$PYSTACHY_LLVM" \
  --output build/program-cache-checks-final.json

"$PY" tools/program_cache_probe.py \
  --compiler ./pystachy --python "$PY" --llvm "$PYSTACHY_LLVM" \
  --benchmark-only --rounds 5 --cpu 0 \
  --output build/program-cache-times.json
```

Run the correctness checks before timing, with no bootstrap or other intentional
heavy workload running concurrently. The probe creates a private temporary
cache, sets its opt-in/trace environment, warms the runtime, and applies the
cleanup scopes above itself. Do not clear the runtime cache between samples.
Its JSON must have `completed: true`, `passed: true`, and no setup error before
using the measurements. For the focused units and existing runtime-cache suite:

```sh
"$PY" -m unittest discover -s tools -p test_program_cache.py
"$PY" -m unittest discover -s tools -p test_program_cache_publication.py
"$PY" -m unittest discover -s tools -p test_cached_run.py
make test-cache PY="$PY"
PATH="$(dirname "$PY"):$PATH" make lint check-runtime PY="$PY"
```

## Scope and remaining limitations

The cached executable is compiled from the ordinary JIT-prepared bitcode with
further LLVM IR passes disabled, then linked with the JIT runtime object. This
preserves constructor execution and retains the JIT tier's IR decisions.
Ordinary AOT applies a different optimization pipeline, so its launch time is a
separate control rather than evidence that cached JIT and AOT have identical
execution quality.

The supported case is Linux, a native compiler invoked by path, default ORC,
and the recorded default toolchain environment. Hosted compilation, MCJIT,
diagnostics, custom C flags/build environments, CPython embedding and external
native libraries bypass the cache. The prototype records consumed toolchain
files but does not provide a hermetic SDK: the toolchain search layout must
remain fixed, and arbitrary wrappers must declare their underlying inputs.
Adding a new higher-priority system header or linker input is outside those
recorded-file checks.

The cache is private to its user; checksums detect accidental damage, not a
malicious same-user writer. Eviction, shared/remote caches, cross-host reuse and
deduplicating simultaneous misses remain open. Old executables and interrupted
staging directories remain until cleanup. Details are in
[the cache documentation](../../../docs/program-cache.md).

Five rounds on one host and four bounded workloads establish only the measured
launch behavior. This report does not measure cold-runtime installation,
long-running execution quality, peak RSS, multicore scaling, or a release-wide
application suite. Initial hashing, source validation and first compilation
remain real costs; the cache helps only after a compatible native program has
been produced and its inputs remain valid.
