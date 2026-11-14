# Testing and verification

Supported programs are checked against CPython in both JIT and AOT modes. The suite also
checks rejected programs, documented deviations, the self-hosting fixed point and runtime
contracts. Use the CPython version in `.python-version` and install the development tools
with `python3 -m pip install -r tools/requirements-dev.txt`.

For user-authored pytest-style tests, the experimental [native pytest runner](pytest-native.md)
collects a bounded source subset, generates typed calls and fixtures, and compares
native phase outcomes with the original files under CPython pytest. Run its
hosted/native parity and failure controls with `make test-pytest-native`.
`make test-pytest-workloads` applies shared pytest assertions to maintained
application and pyperformance APIs, comparing each independent suite with
CPython pytest in JIT and AOT modes.

## Commands

Run these from the repository root:

| Command | Purpose |
|---|---|
| `make` | Bootstrap the native compiler; successive compilers must emit byte-identical IR for the compiler and subset runtime. |
| `make test` | Run the differential, rejection and deviation suite with the native compiler, JIT and AOT. |
| `make test-py` | Run the same suite with the compiler hosted by CPython. |
| `make coverage` | Measure which statements and branches of the compiler's source that suite, the FFI and runtime-cache suites, the IR checks and the compiler's unit tests run, in the CPython-hosted compiler ([compiler coverage](#compiler-coverage)). |
| `make runtime-coverage` | Measure which lines and branches of the runtime's C code the corpus's programs and the FFI suite run ([native runtime coverage](#native-runtime-coverage)). |
| `make variants` | Run the suite, JIT and AOT, in configurations that verification does not test: combinations of IR passes turned off, and the runtime and AOT programs built at `-O0` ([configuration variants](#configuration-variants)). |
| `make verify` | Run the complete verification plan and write `build/verification.json`. |
| `make check-fast` | Run Ruff, mypy and selected hosted compiler unit tests; no LLVM or native build needed. |
| `make lint-python` | Run Ruff only. |
| `make lint` | Run Ruff, ShellCheck and Clang warnings. |
| `make typecheck` | Run mypy on the Python compiler and its entry point; no native build needed. |
| `make check-recordings` | Check expected outputs, remaining deviations, unchanged upstream sources and test-tree hygiene. |
| `make test-cache` | Check runtime build-cache reuse, invalidation and failed-build handling with both compilers. |
| `make test-program-cache` | Check default native program reuse, source/toolchain invalidation, setting keys, fresh execution, concurrency, eviction and failure recovery. |
| `make test-ffi` | Check C calls, FFI diagnostics, embedded CPython (`pyobj`) and CPython extension modules. |
| `make check-ir` | Check the typed IR and its LLVM lowering across the compiler corpus. |
| `make check-runtime` | Check runtime declarations, effects and source agreement. |
| `make irsame REF=<commit>` | Compare IR, diagnostics and exit status with a reference compiler for a refactor. |
| `make bench-extended-check` | Check the extended benchmark runner and CPython/JIT/AOT checksums; no timing thresholds. |
| `make bench-pyperformance-check` | Check the pyperformance runner, ported benchmarks' CPython/JIT/AOT output, and shared pytest API assertions; no timing thresholds. |
| `make bench-match-check` | Check literal, tuple and dataclass `match` dispatch against handwritten branches under CPython/JIT/AOT, including mixed and skewed inputs; no timing thresholds. |
| `make test-pytest-workloads` | Run independent example and pyperformance pytest suites in JIT/AOT, with original CPython pytest as the oracle; no skipped or xfailed workload cases. |
| `make example-cli-check` | Check real example command lines against pinned CPython, JIT and AOT, plus JSON repair process cases, a native replay of the JSON repair corpus and the agent's loopback HTTP transport. |
| `make blas-check` | Check the optional `cblas_dgemm` adapter (`examples/ndarray`) against NumPy and nanoGPT's BLAS backend against its scalar one, under CPython, JIT, AOT and GC stress; needs an LP64 `libblas.so.3` and NumPy. `LD_LIBRARY_PATH` selects the provider; CI checks OpenBLAS and the reference BLAS. |

For quick local feedback, activate the environment with the dependencies from
`tools/requirements-dev.txt` and run `make check-fast`. It runs Ruff, the existing
mypy gate, compiler effect-summary tests (`tools/test_function_summaries.py`), and
all typed-IR unit tests (`tools/test_typed*.py`) under the interpreter selected by `PY`. It builds no native
compiler and needs no LLVM tools. This is a hosted subset; use the full verification
plan for bootstrap, JIT/AOT, GC and runtime evidence. `make check-fast lint` also
runs ShellCheck and Clang warnings, sharing the Ruff prerequisite. Ruff also rejects
obsolete `# noqa` suppressions with `RUF100`.

For a focused edit, select the affected cases:

```sh
make test FILES="tests/programs/strings/str_*.py tests/errors/runtime/rtmode_*.py"
make test-py FILES="tests/programs/strings/str_*.py tests/errors/runtime/rtmode_*.py"
tests/run.sh ./pystachy jit tests/programs/library/lib_fnmatch.py
```

`PYSTACHY_JOBS` controls test workers; the default is one per CPU. Full verification retains
all coverage even when CI distributes the work across jobs. `PYSTACHY_CASE_TIMES=FILE` makes
`tests/run.sh` append each case's wall-clock milliseconds to `FILE` (`MILLISECONDS CASE`, with GNU
`date`), which [the shards' weights](#continuous-integration) are made from.

The ordinary corpus enables the IR checker and therefore exercises uncached JIT.
`make test-program-cache` separately verifies default misses and hits, requiring
zero frontend and LLVM calls on hits. To run selected ordinary corpus cases
through the default cache, use a private `PYSTACHY_CACHE` and the compiler command
`env -u PYSTACHY_IRCHECK -u PYSTACHY_PROGRAM_CACHE /absolute/path/to/pystachy`.

## Differential tests

Each program is `tests/programs/AREA/NAME.py`, with its expected results beside it. An area is a
directory of tests on one subject (`library`, `classes`, `containers`, `exceptions`,
`optimizations`, `upstream` and others), which the first word of a test's name usually names: put
a new test with the tests whose names it shares, or in `language` for statements, scopes and
functions. Names stay unique across areas, because the runner names a case's temporary files by
them. Rejections are `tests/errors/AREA/NAME.py`, in the same areas. The helper packages that
tests import (`mods/`, `loader/`, `emods/` and others) lie directly in `tests/`, which an importing
test's `NAME.path` names. [`tests/corpus.sh`](../tests/corpus.sh) holds these patterns for every
script that lists the cases. A program or rejection left directly in `tests/` or `tests/errors/`
fails `make check-recordings` and a whole-corpus `tests/run.sh` instead of being skipped.

`tests/run.sh` compares these results for each program `NAME.py`:

| Artifact | Contract |
|---|---|
| `NAME.out` | Exact stdout followed by `[exit N]`, recorded from CPython. |
| `NAME.err`, when present | The final stderr line must match CPython's. Without this file, stderr must be empty. |
| `NAME.in`, when present | Input supplied to the program. |
| `NAME.path`, when present | Module path: `PYTHONPATH` for the recording, `PYSTACHY_PATH` for the compiled test. |
| `NAME.full`, when present | Send stdout to `/dev/full` to check failed writes. |
| `NAME` ending in `_closed_stdin`, `_closed_stdout` or `_closed_stderr` | Start the program with that descriptor closed; CPython's `sys.stdin`, `sys.stdout` or `sys.stderr` is then `None`. |

An AOT build's diagnostics are kept separate from the program's stderr and must be empty.
The runner enables `PYSTACHY_IRCHECK=1` unless explicitly overridden.

Rejections `tests/errors/AREA/*.py` must fail with status 1 and one source diagnostic on stderr:
`FILE:LINE: error: MESSAGE`, containing the expected message from the source's first line. A
`NAME.path` beside a rejection is its `PYSTACHY_PATH`.
A traceback containing that message does not pass. Syntax cases also exercise the parse-only
`pystachy check` command; runtime-mode cases use `pystachy rt`.

`tests/deviations/*.py` use hand-written expectations for the
[documented differences](language/compatibility.md#deviations-from-cpython). They are kept apart
from CPython-recorded outputs. The suite covers language behavior, compiler diagnostics,
library APIs, upstream-derived cases, files, exceptions and collector stress. Exact current
counts come from the files and the verification report, rather than a fixed number in this guide.

### Recording expected output

```sh
tests/record.sh NAME
make check-recordings
```

Record differential expectations with `tests/record.sh`; do not edit `.out` or `.err` by hand.
The recorder uses a clean environment, retaining `PATH` and a test's explicit module path.
It rejects a different CPython minor version and warns about a different patch version.

`make check-recordings` re-records into a temporary directory. It fails when an expectation
changes, when CPython now matches a documented deviation, when an unchanged vendored file
fails its recorded upstream hash, or when orphaned artifacts, patch rejects or core dumps
remain in the tree. A deviation that now matches CPython belongs in the differential suite.

## `make verify`

Full verification checks the bootstrap and suite under CPython-hosted and native compilers,
with optimizations disabled, without Python available, under UBSan, and with a collection at
every program allocation. It also runs the contract checks below.

UBSan uses LLVM's compiler-rt builtins (`--rtlib=compiler-rt`) as well as its sanitizer
runtime. Checked 128-bit multiplication on ARM64 needs a helper that libgcc does not
provide. CI checks the shared-library and object-cache JIT paths, including deliberate
overflow and missing-builtin controls, on both Linux architectures. Native thread
stack-size edge cases are compared with the local CPython oracle rather than an
architecture-specific recording.

| Area | Checks |
|---|---|
| Compiler and IR | Valid typed/LLVM IR, runtime ABI and effects, bounded specialization failures, linear compilation, inherited-AST storage and hierarchy comparison code, JIT dead-code removal and inlining, AOT opt-in code retention. |
| Runtime | CPython comparisons for subset runtime functions; dictionary probes and string-hash caching; list storage, shared-container comparisons, file-buffer accounting and streaming consumers. |
| Libraries and interoperability | Regex differential fuzzing and deterministic matcher budgets; FFI calls, embedded CPython and extension modules; runtime build-cache rules. |
| Benchmarks | CPython-equivalent output plus advisory timings. |

The implementation and exact budgets live in `tests/verify.sh` and its named `tools/` probes.
Useful individual checks include `make re-fuzz`, `make re-probe`, `make re-specialize-check`
(matchers generated for random patterns, against CPython's `re`), `make dynany-fuzz`
(seeded programs on [dynamic `Any`](dynamic-any.md) values against CPython, with identity and
containment invariants, plus 30 strict typed/Any parity cases per program, including evaluation
order and first-error traces. The `contracts` group runs three seeds with 150 random cases each,
using the verified native compiler in JIT and AOT, both normally and with program GC stress at
every allocation. `--aot --gc-stress` selects the same configurations locally; the aggregate gate
requires all four modes, 540 cases including 90 parity cases and zero mismatches. This bounded
check complements the full opt-in corpus sweep, `make dynany-optin`), `make dictprobe`,
`make listprobe`, `make eqprobe`, `make fileprobe`, `make streamprobe`, `make jitprobe` and
`make aotprobe` (the runtime's opt-in code that AOT executables keep, by symbol and in a list
store's `-O2` code, plain or not, the allocations `allocelide` lets `-O2` delete and those it
keeps, with the objects they hold, and the allocation window between collections that
`PYSTACHY_GC_MIN` sets).
`make jitprobe` also checks the [JIT runner](internals.md#the-jit-runner) on small C programs
(`tools/test_lljit.py`: its first-use build, cache and `lli` fallback, constructors, `argv`,
status, libraries, objects, archives, errors and signal dispositions; `PYSTACHY_TEST_LLJIT_LLVMS`
adds toolchains of other LLVM versions), and compares JIT launches with CPython under the runner
and under `lli`: inherited descriptors, the program's and its child's whole descriptor tables,
closed standard streams, inherited SIGINT dispositions (sent once the program waits),
shared/object runtime inputs, `-O0` code generation (the runner's, and `llc`'s objects for
`lli`), embedding, temporary cleanup, failed exec and native program-cache miss/hit and AOT
launches.
They use deterministic operation or allocation limits where possible; shared CI runners do
not gate on benchmark speed.

`make python-int-gate` enforces the reviewed promoting-int compatibility baseline across
`tests/programs/`: a fresh pinned-CPython oracle and both JIT and AOT for each entry module
with `# pystachy: python-int`. Its manifest, `tools/python_int_optin_exceptions.json`, names
one case and mode per accepted limitation, with an exact diagnostic, classification, rationale
and tracking issue. New or changed failures, unexpected passes, failed oracles and missing
checks fail the gate. Remove an exception when its case starts passing; never add one to
hide a crash or a wrong result in supported code. `PYTHON_INT_GATE` passes tool options;
`--shard-index 0 --shard-count 3` selects one CI shard. Reports from `--cases` or a single
execution mode are useful for investigation but cannot satisfy CI's full-sweep requirement.

`make python-int-optin` retains the exploratory sweep and `PYTHON_INT_OPTIN="--compare BASE"`
comparison with an earlier report. It can use `--any-python` for local comparisons on another
patch version, unlike the gate, which requires the pinned interpreter. Exploratory reports
never substitute for gate evidence. `tools/python_int_optin.py --gate` invokes the gate too.

`build/verification.json` records each stage's result, duration and counts, plus the source
revision and hashes, toolchain, platform and timestamp. A suite run passes only when its
`passed`, `failed` and `expected` counts prove every expected case ran. Missing stages or
partial coverage fail verification.

The harness sets the options each stage tests and ignores caller options that could change
coverage, listing them in `ignored_env`. It retains `PYSTACHY_LLVM` and `PYSTACHY_JOBS`.
`tests/verify.sh --list` prints the current plan. `tests/verify.sh GROUP` runs one group locally;
run concurrent groups in separate checkouts because they share `build/verify` and the report path.

## IR identity for refactors

`make irsame REF=<commit>` builds and caches the reference compiler in `build/ref/`, then
compares it with `./pystachy`. `make irsame-py REF=<commit>` compares the hosted compilers.
Use `FILES="..."` to select cases; otherwise the corpus includes the compiler, runtime,
differential tests, deviations, benchmarks and compile-only IR probes.

The oracle compares emitted IR byte for byte, rejection messages and exit statuses.
It normalizes each compiler's own library prefix to `lib/` in diagnostic source locations;
diagnostic text, line numbers, unrelated paths and IR remain significant. Each compiler
still reads its own library and runtime inputs. Direct executables and Python script
commands have their homes recognized; unfamiliar wrappers keep raw comparisons.
Messages with quoted library paths or ambiguous quoting also stay raw so normalization
cannot hide a change to diagnostic prose.
Use it when a refactor should preserve code generation. An intentional optimization can
change IR and needs behavioral tests instead.

`make check-ir` verifies typed-IR structure, LLVM acceptance, and the effect summaries,
runtime calls, function attributes, field TBAA tags or calls of compiled functions recorded for
`tests/ir/*.py` (`NAME.fx`, `NAME.calls`, `NAME.attrs`, `NAME.tbaa`, `NAME.inline`). These probes
compile without running;
`tests/ir/pending/` holds probes for open bugs.

## Syntax errors against CPython

`tools/syntax_sweep.py` compares `pystachy check` with CPython's `compile()` without running
the sources. Give it files, directories or snippet files separated by `----` lines:

```sh
python3 -I tools/syntax_sweep.py --compiler ./pystachy /usr/lib/python3.13
```

It reports diagnostic differences separately from valid Python that Pystachy cannot parse.
Current boundaries are in [syntax checks](language/semantics.md#syntax-errors). Earlier test
counts and syntax-survey results are retained as [historical snapshots](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/archive/verification-snapshots.md).

## Compiler coverage

`make coverage` measures which statements and branches of `src/pystachy_compiler/` the
compiler's tests run, with the CPython-hosted compiler under
[coverage.py](https://coverage.readthedocs.io/), pinned in `tools/requirements-dev.txt`. It runs
five suites, each under a coverage.py context of its name:

| Suite | Runs |
|---|---|
| `corpus` | The differential, rejection and deviation suite, JIT and AOT (`tests/run.sh`, as `make test-py` does). |
| `ffi` | `tests/ffi/run.sh`, JIT and AOT: C calls, FFI diagnostics, embedded CPython and extension modules. |
| `cache` | `tests/cache.sh`: the runtime cache's rules and the driver's search for LLVM and for itself. |
| `unit` | The compiler's unit tests, `tools/test_typed*.py` and `tools/test_function_summaries.py`, and those of code that the hosted corpus does not run: the native program cache's (`tools/test_program_cache*.py`, `tools/test_cached_run*.py`, `tools/test_cache_toolchain.py`), `--emit-ir`'s (`tools/test_retained_ir.py`), the C runtime cache's (`tools/test_runtime_c_cache.py`), `tools/test_ctypes_schema.py` and `tools/test_source_lines.py`. |
| `ir` | `tools/check_ir.sh` on the programs the corpus does not compile: `pystachy.py` and `runtime.py`, as the bootstrap's first stage compiles them, the benchmarks and the `tests/ir/` probes with their effect, call, attribute and TBAA contracts. |

`FILES="..."` selects corpus cases and runs the corpus alone; `COVERAGE_SUITES` names the
suites to run. The results go to `build/coverage/`:

| File | Contents |
|---|---|
| `html/index.html` | Each module's source, marked line by line, with the suites that ran each line. |
| `summary.md` | The commit; statement and branch coverage, in all and for each suite alone; what only the other suites run; a table of the modules, with the corpus's own total beside each. |
| `coverage.json` | coverage.py's JSON report. |
| `badge.json` | Statement and branch coverage, as a [shields.io endpoint](https://shields.io/badges/endpoint-badge). |
| `parts/` | Each suite's data (`data.PART`), counts (`PART.json`) and test report (`PART.log`). |

The percentages are **hosted compiler coverage**: the compiler's own source, as CPython runs
it, statements and branches apart. coverage.py's own total, which the summary also gives,
counts both together. None of it measures `runtime.c`, `runtime.py`, `lib/` or the compiled
programs, which run as native code ([native runtime coverage](#native-runtime-coverage)
measures `runtime.c`'s). The native compiler's runs in `make verify` (its own bootstrap stages,
the sanitizer, Python-free and collector-stress stages) add nothing to it either, though they
run the same compiler code. The [native program cache](program-cache.md) (`program_cache.py`,
`cached_run.py`, `cache_toolchain.py`) serves only the native compiler: `pystachy run` under
CPython bypasses it, so only the `unit` suite measures it, and what only a native run reaches
(recording a miss's toolchain inputs, launching a cached program) stays unmeasured.

[`.coveragerc`](../.coveragerc) holds the settings. Each compiler process starts through a
launcher that counts it and writes its own data file. `pystachy run` replaces its process with
`lli` through `os.execv`, so coverage.py saves the data first (`patch = execv`); without that,
JIT runs record nothing. A suite fails unless every process left data, but for the one build
that `tests/cache.sh` kills on purpose. `tests/cache.sh` runs a copy of the compiler in a
directory of its own, which `[paths]` maps to `src/`. Each suite starts with an empty runtime
cache, so the runtime's build is measured too. `make coverage` fails when a test fails or data
is missing, never because of a percentage: there is no threshold.

`COVERAGE_SHARD=I/N` limits the corpus to shard `I` of `N`, as `tests/verify.sh` shards it
(`tools/shard_cases.sh`), and `COVERAGE_REPORT=0` leaves out the report.
`tools/coverage_report.py` combines such parts later. It first checks that every part passed
with complete data, that no suite was measured twice, that no shard is missing and that all
parts measured one commit.

## Native runtime coverage

`make runtime-coverage` measures which lines and branches of the runtime's C code the programs
run: `runtime.c` with the `ryu/` and `mpz/` files it includes, `pyembed.c` (embedded CPython) and `pyext.c`
(the extension-module ABI). It builds a new runtime cache with clang's
[source-based coverage](https://clang.llvm.org/docs/SourceBasedCodeCoverage.html)
(`PYSTACHY_CFLAGS="-fprofile-instr-generate -fcoverage-mapping"`), then runs the corpus's
programs, JIT and AOT, and the FFI suite, AOT, with the native compiler. It needs clang's
profile runtime (Ubuntu's `libclang-rt-18-dev`, which `tools/setup.sh` installs) and LLVM's
`llvm-profdata` and `llvm-cov`. `FILES="..."` selects corpus cases. The results go to
`build/runtime-coverage/`: `html/` (llvm-cov's annotated source, with branch counts),
`summary.md` (lines, branches, functions and regions for each file and for each section of
`runtime.c`: the collector, strings, arithmetic, lists, dicts, sets, I/O, exceptions and the
rest), `coverage.json` (llvm-cov's summary), `lcov.info`, `badge.json` and `parts/`: each part's
(a suite's, or a shard's of the corpus) profile, counts and log. `RUNTIME_COVERAGE_SHARD=I/N` and
`RUNTIME_COVERAGE_REPORT=0` measure one part, as for the compiler's coverage, and
`tools/runtime_coverage.sh --report` combines the parts in `parts/`. It first checks that every
part passed with a profile, that no suite was measured twice, that no shard is missing and that
every part measured the commit whose sources the report's objects are compiled from.

Each instrumented program adds its counts at exit to one profile for each kind of binary (the
JIT tier's shared runtime, AOT executables, extension modules); a program that ends by a signal,
`_exit()` or `os.execv` adds none. The driver compiles a copy of `runtime.c` behind a `#line`
directive, which clang's coverage mapping does not follow, and `pyembed.c` and `pyext.c` from
standard input. llvm-cov therefore reads the counts through objects compiled here from the
sources themselves, with the same flags: clang finds a function's counters by its name and a
hash of its body, and a function whose body differs from its source's (llvm-cov's "mismatched
data") fails the run. `runtime.py`, which Pystachy
compiles, carries no instrumentation and is not measured, nor are the C probes (`make dictprobe`
and the others), which compile `runtime.c` under macros of their own. As for the compiler's
coverage, a failed test fails the run and no percentage does.

The instrumented runtime's machine code differs from the normal build's, and so do the stack
words and registers that the conservative collector scans; the corpus must pass all the same.
Running it so found that `open()` could keep alive the unreachable writer that it collects to
close, where register allocation left that writer in a callee-saved register across the
collection.

## Reading coverage

Coverage shows which code ran, not that it ran correctly. The differential tests, rejection
fixtures and collector stress check results; a covered line can still miss a combination of
types, an optimization pass or an exception path. A missed line is either untested behavior or
code that only runs outside these suites, which the per-suite figures and the report's contexts
help tell apart. Coverage is advisory: no check requires it and no change has to raise it, while a
fix still needs a regression test that fails without it ([contributor guide](../CONTRIBUTING.md#validation)).

What a change adds is reviewed where it is: with `COVERAGE_BASE=REF` (for example
`make coverage COVERAGE_BASE=origin/main`), either summary also lists the code changed since the
merge base of `REF` and `HEAD`, uncommitted changes included, that no suite ran: its statements or
lines not run and its branches not taken. Review those before any threshold on the total. The
Coverage workflow lists them for a manual run on a branch
(its `base` input, `origin/main` by default). A selection (`FILES=...`) runs less of the suites, so
it lists more.

The [Coverage workflow](../.github/workflows/coverage.yml) runs both measurements daily and on
demand, and on pushes to `main` that change its setup or the suites' runners. PRs do not launch
this exhaustive matrix; run it manually on a PR branch when coverage detail is needed.
The compiler's coverage runs in twelve parallel jobs (the corpus in ten shards, the FFI and IR
suites in one, the runtime-cache and unit suites in another) and the runtime's in seven (the
corpus in six shards and the FFI suite), following one verified compiler producer; a report job
for each combines its parts. As for CI's groups, each job targets under ten minutes of work
within a 15-minute limit. Job summaries show the summaries, and the reports are workflow
artifacts. After each run on `main`, a separate job, which runs no
tests, commits the summaries and badges of the reports that passed to the `badges` branch, which
the README's badges read:
[`coverage.md`](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md) and
`coverage.json`,
[`runtime-coverage.md`](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)
and `runtime-coverage.json`.

## Configuration variants

`make variants` (`tools/variants.sh`) runs the differential, rejection and deviation suite, JIT
and AOT, in configurations that `make verify` does not test and that must change no result:

| Variant | Configuration |
|---|---|
| `opt-1` … `opt-6` | `PYSTACHY_OPT` turning off the IR passes that each row of a covering array of their pairs leaves off. Verification runs every pass on and all of them off (`-all`); with these six rows, every two passes run in each of their four on/off combinations. A pass added to `OPTS` gets a column of its own; the rows have room for fifteen passes (`tools/variants.sh`). |
| `cflags-O0` | `PYSTACHY_CFLAGS=-O0`: the runtime unoptimized, and with it an AOT program's whole module, whose IR then runs as the compiler emitted it. The runtime's frames keep every local in memory, which changes the dead words that the conservative collector scans as roots. Its JIT runs in `lli` (`PYSTACHY_JIT_LAUNCHER=lli`), the fallback of the [JIT runner](internals.md#the-jit-runner) that verification and the other variants use. |

`make runtime-coverage` is another variant: clang's instrumentation changes the runtime's register
allocation, and only that build showed `open()` keeping alive the writer it collected to close
(`tests/programs/runtime/rt_list_vacated.py`). With the fix reverted, the runtime built at `-O0`, `-O1`, `-O3`,
`-Os` or `-Oz`, or with LLVM's basic or PBQP register allocator, still passes.

`VARIANTS="opt-1 cflags-O0"` selects variants, `FILES=...` cases, `VARIANTS_SHARD=I/N` a shard of
the corpus (`tools/shard_cases.sh`) and `MODES=jit` one tier. The script drops the caller's
settings that verification drops, builds each variant's runtime in a cache of its own and writes
the logs to `build/variants/`, so run one at a time in a checkout. Each variant takes about as
long as `make test`. The [Variants workflow](../.github/workflows/variants.yml) runs each one in
four shards (24 consumer jobs plus one compiler producer) daily, on demand and on relevant `main` pushes. The lighter `opt-1`
and `cflags-O0` rows share one build per shard; the slower optimizer rows run separately
within the 15-minute job limit. PRs run the seven
configurations on representative and changed cases in **two workers**, reusing the verified
bootstrap. Each worker runs three or four configurations with private runtime caches and records its
exact cases and results. The PR aggregate requires both workers to pass.

Each full Variants artifact includes `worker.json` with that consumer's CPU, source commit,
toolchain, shard, configurations and outcome. Use these identities with the workflow's job
execution times when comparing headroom; a producer's CPU does not identify its consumers.

Variants and native runtime coverage each build the default compiler once per workflow run.
Consumers validate the source/commit, LLVM and Python versions, Linux ABI, run identity and
payload checksums with `tools/verification_bootstrap.py` before execution. Runtime caches
stay private: variants still build every selected runtime configuration, and coverage still
builds each instrumented runtime. Hosted compiler coverage remains independent. No compiled
binary or successful test/proof result is reused between runs.

## Continuous integration

The [CI workflow](../.github/workflows/ci.yml) runs on pull requests (including forks), pushes
to `main` and manual dispatch. Pull requests test the branch merged with the then-current
`main`. A newer PR push cancels its previous run; commits on `main` run to completion.
Markdown/docs-only PRs run Lint and submission format checks plus a lightweight
`Verification` check. The legacy DCO job always skips pending branch settings. The x86-64
bootstrap worker classifies the tested merge commit's changes against its base. The
documentation plan skips toolchain setup, builds and verification/variant workers.
The full-only qualification job skips on every PR. Renaming a source file into `docs/`
still selects code verification.
Classification verifies the immutable event merge SHA and its PR-head parent. If
GitHub generated that merge against a newer base than the event payload records,
CI requires code verification and uses the validated merge's first parent for changed-case
selection. A wrong checkout, wrong PR head or non-merge commit fails classification.
Other PRs use the compact profile below. Pushes to `main` and manual CI runs retain
complete verification for the release gate.
The toolchain is Ubuntu 24.04, LLVM 18 and the CPython version pinned in `.python-version`.

The top-level `bench/*.py` step requires successful CPython, JIT and AOT runs with
identical stdout and stderr. AOT builds must succeed silently and produce a fresh
executable. The aggregate independently requires every benchmark in the checkout
exactly once, matching program/parity counts and finite positive timings for all four
phases; these are evidence checks, with no speed threshold.

The `benchmarks` group also runs `make bench-pyperformance-check` with that run's verified
native compiler. Every delivered adaptation must match CPython stdout in JIT and AOT on
bounded smoke inputs; a mismatch or failed build fails the group and aggregate gate.
It also runs the shared pytest API assertions for all 28 delivered workloads.
The group's artifact includes `pyperformance-smoke.json` and `pytest-pyperformance.json`. This is correctness coverage,
with no timing thresholds or claim to run the upstream pyperf harness.

The same group runs `make bench-match-check`: six workload/distribution combinations
validate literal, tuple and dataclass patterns against equivalent handwritten branches
under CPython, JIT and AOT. The controller rejects mismatched checksums, work counts and
unexpected output. Its `match-dispatch-smoke.json` artifact is correctness evidence;
paired performance and optional pyperf measurements have separate reproduction commands
in [the match benchmark](../bench/match_dispatch/README.md).

The PR `opt-in` worker and full-run `hosted` jobs run 20 independent example API suites through
`make test-pytest-workloads PYTEST_WORKLOAD_ARGS='--group examples'`, reusing the
verified compiler. Splitting these checks between existing jobs leaves more room
within the 15-minute budget without adding workers. `pytest-workloads.json` records every
original-pytest comparison. The Make targets use `PYTEST_WORKLOAD_JOBS=4`; the suite
runner also accepts `--jobs 1` for a serial replay. Each worker uses one compiler process
and a private runtime cache. Results retain the selected suite/mode order, failures keep
the complete inventory, and cancellation terminates only this invocation's process groups.
Missing modules/results, empty suites, skips, xfails and failed builds fail this
check. These tests supplement the exact CLI, FFI, upstream-reference and timing
contracts below; they do not replace those distinct observations.

The x86-64 PR `opt-in` worker (full-run `hosted`) also runs `make test-pytest-native` with the verified compiler
and pinned original pytest oracle. Its JIT examples retain the hosted compiler; repeated
native builds use `PYTEST_NATIVE_COMPILER="$PWD/build/verify/pystachy2"`, with `PYSTACHY_HOME`
pointing at the checkout. Test modules run first, at most four at once. Only after they
finish do the JIT examples, AOT examples, failure controls and bundled upstream methods
run together, each with its own work directory. This ordering prevents tests from
competing with examples for the default directory's lock. The checks cover collection, fixture lifecycle,
JIT/AOT parity, GC stress, failure controls and the bundled upstream fnmatch/textwrap
methods. The existing job runs once on code PRs, main pushes and manual runs;
documentation-only PRs retain their lightweight plan. Its artifact includes both
example-mode reports, `pytest-controls.json` and `pytest-upstream-bundled.json`.
Keeping this check outside Lint preserves the same coverage within the existing
job, worker and 15-minute limits.

The `example-cli` verification step runs in the `benchmarks` group: on x86-64 in
PR CI and on both architectures in full CI. `tools/check_example_cli.py` runs 24 tiny cases through
the actual `csvstat`, `latency`, `mailmerge`, `topk`, `urlstats` and `route` entry points.
These cover file loading, successful options, usage errors and rejected inputs;
every exit status, stdout byte and stderr byte must match the fresh pinned-CPython
oracle in JIT and AOT. The input fixtures must remain unchanged. Options that print
elapsed time are excluded, apart from the router's empty in-memory batch with its
defined zero-time report.

The step also invokes the existing `tests/upstream/json_repair/cli.py` checks (20
process cases, including output-file effects, compared with CPython in JIT and AOT),
replays the 943 recorded calls of the [JSON repair corpus](../tests/upstream/json_repair/README.md)
through native JIT and AOT builds of the port, each checked by `tools/json_repair_parity.py`
against the recorded CPython outcomes, and runs
`examples/agent/http_smoke.py` with CPython, JIT and AOT launchers. The latter
validates five requests against a local HTTP server, the response transcript and
the resulting workspace repair; it needs `curl` but no model service or credentials.
This is deterministic transport and execution coverage, with no performance threshold.
Each command has a timeout that terminates its process group, including children.
Failures identify the case, execution phase, command, timeout, exit status and both
output streams. `build/verify/example-cli.json` records completed case identities
and integration modes; verification and the aggregate gate reject missing or
duplicated work even if the enclosing step claims success.

For the same check locally, use `make example-cli-check` with `PY` set to the pinned
interpreter. `BENCH_COMPILER=build/verify/pystachy2` reuses a compiler verified from
the current tree. The runner uses a private temporary fixture directory, clears
inherited compiler options and shares its runtime cache across its small commands;
`--cache` can select an isolated cache for concurrent work.

The independent [Performance smoke workflow](../.github/workflows/performance.yml) runs on
main pushes, weekly schedules and manual dispatch, outside the PR budget. One job measures eleven small workloads:
scalar autograd, dense projection/softmax, fnmatch, mixed JSON parsing, repair-style scanning,
integer/float copies and mutable-global reads in a dynamic-Any opt-in module without observed identity,
heterogeneous cyclic graph deep-copy/checksum processing, and the
existing adapted pyperformance `regex_effbot`. The [kernel notes](../bench/smoke/README.md)
map each case to its coverage and limits. It builds each revision's
native compiler once, then compares a main push against its previous SHA, or a scheduled/manual
run against its selected reference, on one CPU with separate warmed caches and identical head workload sources.
This is a performance probe, not another bootstrap verification stage.

Each workload checks output against CPython and records three alternating base/head pairs:
JIT process/loop and AOT process/loop time. AOT build time is measured for each source file
on its first workload; later modes reuse those binaries. The graph case's loop metric is
processing CPU time, excluding graph construction; other loop metrics are wall time.
Each result records its `loop_clock`. A slowdown of at least 20% and 5 ms
triggers three more pairs. Both batches must meet the threshold with disjoint sample ranges
to emit an advisory Actions warning; other threshold crossings are `unconfirmed`.
Correctness, setup and measurement errors fail the job. Timing warnings do not gate merging.
Peak RSS and retained-memory costs remain separate measurements; this suite records timing.
The step summary and 30-day `perf-smoke` JSON artifacts retain revisions, toolchain, source
hashes, raw samples and same-run CPython controls. The job allows 15 minutes for both
compiler builds, warmups and any confirmation batches. Atomic JSON checkpoints preserve
completed workloads during execution. Their `status` is `incomplete` until every workload
and the summary finish, `error` if a caught exception is recorded and re-raised, or
`complete` after success; `phase` identifies the current or last stage. A cancelled process
can leave an `incomplete` checkpoint, which must not be treated as a complete comparison.
There is no cross-run download or extra dependency. Locally on Linux, use
`python3 tools/perf_smoke.py --base /path/to/baseline --json build/perf-smoke.json`.

Weekly runs (Monday 08:23 UTC) compare current `main` against the fixed reference
`80840d264b2d4e76c21a8deec6db90ce6e3c5b22` from #853. Manual dispatch defaults to this
reference too, with an optional baseline override. Both revisions are rebuilt and measured
on the same runner each time; ratios therefore include cumulative changes since the reference.
These separate runs retain `perf-reference` raw JSON artifacts for 90 days, providing a bounded
history without adding work to PR or push runs. Download them from the workflow's run pages.
Compare a series only with matching reference, workload sources/arguments, measurement code
(including imported helpers), Python/LLVM and CPU/platform; do not gate on old absolute times.
Changing the reference or measurement inputs starts a new series. Keep the pin explicit rather
than automatically advancing it after a slowdown. This does not add a permanent history store.

Historical absolute times are unsuitable as gates: in the retained
[October 16 snapshot](benchmarks/pyperformance-2026-10-16-a74faae.json), 16 of 17 usable
AOT workloads had over 20% within-revision wall-time spread (excluding removed `deltablue`
and optimized-away `unpack_sequence`). This small monitor does not cover memory, full models,
end-to-end json_repair or all examples; broader benchmark history remains under #45.

### PR budget

A code PR can create **19 workflow job rows**, including the skipped full-only qualification
and legacy DCO jobs, plus the submission format job. Its separate `Submission format` commit
status uses no runner. Lint enforces at most **19 jobs across all PR workflows**, **four native
AOT shards and two workers per other task group**, and **15 minutes per job**
(`tools/test_workflow_limits.py`). Path filters cannot hide a matrix
from the budget. Each test runner uses at most four processes within its worker.

| PR work | Jobs | Coverage |
|---|---:|---|
| Linux bootstrap | 1 | x86-64 compiler/runtime fixed points and verified compiler bundle. |
| Hosted | 1 | Every corpus case: hosted/native IR, diagnostics and check parity; hosted driver end-to-end strata. |
| Native AOT | 4 | Disjoint quarters of the **complete** corpus in AOT; the fourth worker also checks scaling's second half. |
| Native JIT and variants | 2 | Disjoint halves of the **complete** corpus in JIT, then seven sampled configurations split across the same workers; the first then checks native program-cache invalidation and execution, the second runtime ABI, cache and GC controls. |
| Safety | 2 | Representative and changed cases: optimizer off, Python-free rebuild, UBSan rebuild, JIT/AOT GC stress; generated ASan controls on the second worker. |
| Opt-in compatibility | 1 | Selected programs with dynamic `Any` and promoting ints, against fresh CPython oracles; shared pytest example APIs and native runner qualification. |
| Contracts | 1 | Complete IR/runtime/FFI and behavioral contract checks; bounded Lean null/union proofs. |
| Cache and compiler GC | 1 | Both runtime-cache checks, then stressed self-compilation. |
| Benchmarks and scaling | 1 | Correctness, scaling's first half, BLAS and large upstream regex. |
| Full-only qualification | 1 skipped | O1 bootstrap comparison and native archive smoke run on main/manual CI. |
| `Verification` | 1 | Confirms the selected plan. For code PRs, checks reports, profiles, selection manifests, counts and job results. |
| Lint, legacy check and submission format | 3 | Lint includes CPython port preservation and selected Lean kernel/checker controls. DCO always skips; submission format validates metadata and sends an acknowledgment reminder. |

`VERIFY_PROFILE=pr tests/verify.sh GROUP` selects this plan; plain `make verify` stays exhaustive.
`tools/ci_sample.py` selects deterministic representatives and changed/new cases, including
surviving cases affected by removed or moved fixtures. Workers and the gate use the same
`CI_BASE_SHA` and independently validate the selected manifest. Secondary configurations are
sampled; the normal native suite is not. PR reports explicitly identify the
`pr` profile and cannot certify full verification.

The two JIT/variant workers reuse the same verified bootstrap as the verification groups.
Every consumer checks source bytes, commit, architecture, toolchain,
workflow run and artifact hashes. Runtime caches stay private; Python-free and sanitized builds
remain independent. Pip downloads are cached by the pinned dependency files.
The separate full-run qualification job reuses that run's x86-64 bundle and runs
`python3 tools/check_bootstrap_tier.py build/ci-bootstrap`.
It forces the production Make recipe to rebuild with an O1 temporary compiler and an O2 final
compiler, using the same checkout and a private runtime cache. All three compiler and all three
runtime witnesses must match the standard bundle byte for byte; no path normalization is used.
The check revalidates source, toolchain and run identity after the build and requires the standard
bundle and verification report to remain unchanged. Consumers continue using the standard O2
bundle. The separate `build/bootstrap-tier/report.json` and `make.log` are uploaded as
qualification evidence. Build durations and final executable hashes are diagnostic; performance remains
inconclusive until controlled measurements. Lint separately executes scalar and allocating native
programs at O0, O1 and O2, both normally and with program GC stress. These checks preserve the
existing job/worker/time limits and do not qualify lower tiers for general application use.
PR native work uses two JIT halves and four AOT quarters, each with one execution mode.
Both modes retain every corpus case; the inexpensive rejection and parser checks repeat.
The aggregate requires every exact case/mode pair once and the producer's bootstrap identity,
including the native baselines deferred by opt-in checks. The JIT workers upload their native
reports before running their existing sampled configurations in sequence. CI creates 16 job
rows, including the skipped qualification row; all PR workflows together create 19.
The compact cache/GC group finishes both parallel cache checks before starting its
collector-stressed self-compilation, preserving the latter's ten-minute bound without
three competing compiler processes.
Native program-cache checks run last in the first JIT worker, with the stage-2 compiler
its corpus half restored. [Issue #1178](https://github.com/den-run-ai/pystachy/issues/1178)
records historical slow jobs and the measured headroom acceptance criteria; configured
limits alone do not establish current run times.

### Full verification

Pushes to `main` and manual runs execute all thirty-four verification groups on both Linux
architectures. They provide the exact-commit evidence required for releases. Local groups build
their own bootstrap; CI builds it once per architecture. Large upstream regex runs alongside
benchmark correctness, and Lint checks CPython port preservation. The full groups are:

| Group | Work after bootstrap |
|---|---|
| `hosted` | The CPython-hosted compiler against stage 2 on every corpus case: identical IR, messages and exit status (`tools/irsame.sh`) and `check` results (`tools/irsame.sh --check`); one case in 64 and a program of each hosted-driver path after the IR also run end to end, JIT and AOT. |
| `native-0`, `native-1`, `native-2` | Three disjoint thirds of the native differential suite, JIT and AOT. |
| `opt-off-0`, `opt-off-1`, `opt-off-2` | Three disjoint thirds of the native suite with IR optimizations disabled. |
| `python-free-0`, `python-free-1`, `python-free-2`, `python-free-3` | Rebuild with no Python on `PATH`; four disjoint quarters of the suite with that compiler. |
| `ubsan-0`, `ubsan-1`, `ubsan-2`, `ubsan-3`, `ubsan-4` | Sanitized compiler/runtime; five disjoint fifths of the JIT/AOT suite. |
| `gc-self` | Collector-stressed self-compilation and identical-IR check. |
| `gc-ir-0`, `gc-ir-1` | Two disjoint halves of the corpus: the compiler collecting every 1,000 allocations gives stage 2's IR, messages and exit status for every case and stage 2's `check` results. Both halves also compare `runtime.py`. |
| `gc-jit-0`, `gc-jit-1` | Two disjoint halves of the JIT suite with program GC stress, one case in 16 of each half with the compiler stressed too. Execution uses its own weighted partition, independently of the identity halves. The x86-64 `gc-jit-0` job then runs runtime ABI, cache, GC and generated-code ASan controls. |
| `gc-aot-0`, `gc-aot-1`, `gc-aot-2` | Three disjoint thirds of the AOT suite with program GC stress, one case in 16 of each third with the compiler stressed too. |
| `dynany-optin-0` through `dynany-optin-2` | Three disjoint thirds of `tests/programs/`, opted into dynamic `Any`, compared with a fresh pinned-CPython oracle in JIT and AOT. |
| `python-int-optin-0` through `python-int-optin-2` | Three disjoint thirds of `tests/programs/`, opted into promoting ints, with a fresh pinned-CPython oracle in JIT and AOT and exact reviewed limitations. |
| `runtime-cache` | The cached runtime's rules with both compilers, the two runs side by side; annotation-widening parity with CPython, native JIT/AOT and focused GC checks; then native program-cache invalidation and execution. |
| `contracts` | Runtime, IR, library and resource-bound checks, including 540 seeded dynamic-`Any` cases (90 typed/Any pairs) in JIT/AOT, normally and with program GC stress; independent steps run side by side. |
| `benchmarks` | Benchmark correctness/timings, real example CLI parity, JSON repair process cases and agent loopback HTTP; extended correctness checks reuse the verified compiler. |
| `scaling` | Every compiler-scaling shape, in two steps, shapes measured side by side. |

GC identity and JIT execution have separate job budgets. The aggregate still requires
both identity halves and every execution shard; case selection and stress intervals
are unchanged. The PR matrix retains its existing groups and budget.
A failed group leaves the others running. The aggregate checks are
`make verify (Linux x86-64, LLVM 18, Python 3.13)` and
`make verify (Linux ARM64, LLVM 18, Python 3.13)`. For pull requests, maintainers
verify `Verification` and `make lint (ruff, shellcheck, clang -Wall -Wextra)` on the
current revision before merging. Branch protection requires both checks, including
for administrators. Remove the retired DCO check in GitHub settings; until then it
remains as an always-skipped compatibility job.
[Issue #766](https://github.com/den-run-ai/pystachy/issues/766) records the enforcement
work; [CONTRIBUTING.md](../CONTRIBUTING.md#ai-assistance-and-review) describes the
review and submission requirements.
Each report gate requires every group to succeed. It rejects missing or unexpected stages,
inconsistent source revisions or toolchains, different bootstrap IR, and missing or
inconsistent bootstrap provenance.
Bootstrap and report artifact names include `x86_64` or `aarch64`; the final report
merger checks that every input names the expected native machine. An x86 report renamed
to look like an ARM artifact is rejected. Combined reports are `x86_64-verification` and
`aarch64-verification`; download the corresponding `MACHINE-verification-*` artifacts
and use `tools/merge_verification.py DIRECTORY --machine MACHINE -o REPORT.json` to
reproduce either full gate. Main and manual runs require both architectures. PRs run the
x86-64 aggregate; full CI and Installation retain ARM64 coverage. To reproduce
the PR aggregate, use `--profile pr --machine x86_64` and the same `CI_BASE_SHA` as the
workflow run. Its combined report is labelled `pr` and requires every compact group. Lint
checks that each profile's group list matches the workflow matrix.
Reports and logs are uploaded as workflow artifacts, together with the generated dynamic-`Any`
fuzzer programs. The gate requires its complete 3-program/540-case budget, including 90 typed/Any
parity cases, all four execution modes, program GC interval 1 and zero mismatches.
`python3 tools/annotation_widening.py --report widening.json` discovers directly called,
undecorated module functions with one return and concrete scalar signatures in dynamic-`Any`
entries. It widens only the parameter and return annotations. It also recognizes the
`list[int] -> Any` boundary and widens its parameter. Imported support modules, declaration
markers, generic and generator signatures, decorated functions and indirect calls keep their
annotations. Each pair must first produce the same successful output with empty stderr under
pinned CPython. Both forms then run against their own recordings in JIT and AOT with the
entry's integer policy. Both profiles require the native-list alias fixture and run it
and the scalar identity fixtures again with collection at every program allocation.
The opt-in worker runs `--profile pr` for focused checks and the full profile on main and release.
Reports give exclusion counts and every qualified function and native result. Expected compiler
rejections require the exact case, mode, diagnostic, streams and status in
`tools/annotation_widening_exceptions.json`. Local shards use `--shard-index` and `--shard-count`.

The dynamic-`Any` opt-in sweep copies the test fixtures into an isolated directory, adds the
opt-in pragma to each selected program and records CPython's output on that same source.
It reuses the ordinary harness's stdin, import-path, `/dev/full`, signal and diagnostic handling.
The committed exception manifest identifies exact cases, execution modes and observed failure
signatures; unexpected passes require removing stale exceptions, and new failures fail the job.
The report gate verifies the full corpus and exception hashes, exact shard membership, every
case/mode result and complete oracle/check counts. Generated copies and failure logs remain in
the workflow artifacts. Run locally with `make dynany-optin`, or select a shard with
`DYNANY_OPTIN="--shard-index 0 --shard-count 3"`. This sweep covers normal JIT/AOT execution;
program GC stress remains covered by the separate generated parity checks and existing corpus.
Both sweeps run a program on every CPU; AOT builds are about 80% of their time. In CI, and in
`tests/verify.sh all`, they pass `--native-suite`: the same run's `tests-native` steps execute
every unchanged program with the same compiler, JIT and AOT, so the sweeps leave to them only the
baseline rerun of an exact expected failure and the AOT check of a program whose opted-in LLVM IR
and fresh CPython recording are byte-identical to the original's (`native-ir` rows, about a
quarter of the corpus). Every JIT check and every other AOT check still runs opted in, and the
aggregate rejects such reports without a complete stage-2 JIT/AOT `tests-native` suite. The logs
list only checks that neither passed nor were left to `tests-native`; the summary line counts the
latter. `tests-native` never runs with GC stress, so `python_int_gate.py` refuses
`--native-suite` with `--gc-stress`.
The promoting-int sweep uses the same isolated-source and CPython-recording contract. Its
report is checked against the current corpus, reviewed manifest and consumed source hashes,
and binds the executed native compiler by its SHA-256. The aggregate rejects missing shards,
duplicate case/mode pairs and inconsistent compiler identities. Promotion regressions added
with their explicit pragma are also included in the existing full GC JIT/AOT suites, which
collect at every program allocation; the normal opt-in sweep does not claim GC-stressed
execution. Artifacts retain each shard's report and reproduced sources for diagnosis.
A failed producer blocks its consumers
and fails the final gate; there is no fallback to an older compiler.

The combined report's duration is bootstrap work plus the longest consumer group's verification work;
`ci.runner_seconds` measures aggregate work. Queueing, setup and other steps add to elapsed
workflow time. The 15-minute limit applies to each verification job.

GC artifacts retain per-case wall times in `verify/gc-ir-N-times.log` (both compiler
invocations and their comparison), with runtime and syntax checks in separate
`gc-ir-N-runtime-times.log` and `gc-ir-N-check-times.log` files. Execution samples
and remaining cases have `gc-jit-N-sample-times.log` and `gc-jit-N-suite-times.log`,
and corresponding `gc-aot` files. Each line is `MILLISECONDS CASE`; timings require
GNU `date` and do not affect the comparison or test verdict.
Identity timings are appended as cases finish, retaining completed work if a later
case reaches the job limit. Their row order can differ between runs.

The full GC identity halves use `tests/gc_case_weights.txt` when present, falling
back to the ordinary case weights otherwise. GC weights measure stressed compiler
work, which can be large for imports whose programs run quickly. JIT halves and
AOT thirds use ordinary JIT/AOT weights for execution and its deterministic
compiler-stressed sample. Changing the identity weights therefore leaves the
execution partition, order and sample unchanged. Each partition covers the full
corpus; the aggregate requires both identity halves and every execution shard.
The PR profile retains its sparse selection. Weight changes affect placement and
order, never coverage or stress intervals.
A GC table `reserve W0 W1` row would supply initial weights before balancing identity
cases, in the table's weight units; a missing table or reserve row means zero reserve.
The current table has none. Its header names the commit and CI run whose x86-64 and
ARM64 `gc-ir-N-times.log` files it was refreshed from: each case's wall time for both
compilations and their comparison, scaled to the median corpus program. JIT samples
also enable the IR checker through `tests/run.sh`'s default.
Refresh GC weights with `tools/case_weights.py -o tests/gc_case_weights.txt` and
both halves' `gc-ir-N-times.log` files from one completed run; runtime, syntax and
execution timings describe different work and should not be mixed into that table.
`tools/case_weights.py` writes case weights only, so it does not carry a reserve into
potentially different units. Identity now has its own jobs; do not reserve JIT work
when refreshing its weights. Check identity balance and each independent job's time
before adopting the refresh.

GC self-compilation collects every 5,000 allocations and has a separate ten-minute bound.
At the former interval of 1,000, it spent 23 minutes on 15,543 full-heap collections;
the wider interval still exercises thousands of collections without dominating CI.
The compiler collecting every 1,000 allocations is checked by identity, once a run: `gc-ir-0`
and `gc-ir-1` run independently of JIT and compile the cases of two disjoint halves of the
corpus (`gc_shard_cases`, balanced as above) with it and with stage 2 unstressed, through
`tools/irsame.sh` (`rt` for `rtmode_*` cases, with the IR check on), and require the same IR byte
for byte, the same messages and the same exit status for every case, the same IR of `runtime.py`,
and the same `check` output and status for every `syntax_*` case (`tools/irsame.sh --check`). The
GC suites then collect at **every program allocation** (`PYSTACHY_GC_STRESS_PROGRAM=1`) and run
every case of the corpus once in each mode, rejection and syntax checks included, compiled by
stage 2 unstressed: JIT in two halves balanced for execution, AOT in three thirds. Each suite used to
compile every case with the stressed compiler, in each mode; where the IR is the same, the LLVM tools
build the same program from it, so the second compilation only repeated what one identity check
shows, at about twelve times the unstressed frontend's cost (on one case in ten of the corpus, on
one core, the stressed frontend took 62% of a GC JIT run and 28% of a GC AOT run). One case in 16
of each job's shard still runs end to end with the compiler stressed too: the cases at positions
4 (JIT) or 12 (AOT) modulo 16 of the shard in weight order, heaviest first. Drawn from
the job's own shard, the sample stays in it when the execution weights change and is
the same on every runner. Its positions do not guarantee a proportional share of
work; the per-case timing logs show its actual cost. Offset 0 would put each shard's
heaviest case in every sample, and the two modes' offsets
differ, so that they stress different cases where their shards' orders agree. The sample runs
first, in a runtime cache of the GC steps' own (`build/verify/gc-cache`, which each run starts
empty), so the stressed compiler builds the runtime that the job's GC tests use, and the driver's
cache, `opt`/`lli` and `clang`/link paths after the IR run under stress; the program-stressed run
takes the shard's other cases. AOT keeps three jobs: projected from the same measurements, two
would each take about 11.2 minutes of work, over the ten-minute target, and three take about 7.7.
Self-compilation, both identity halves and the five execution suites use separate runners
and report their own durations.
The final gate requires all eight groups, both execution modes, the intervals (1,000 for `gc-ir`
and the samples' compiler, 0 for the program-stressed runs' compiler, 1 for every program),
distinct shard identities, each sample's identity (its period and its mode's offset, as many
cases as its shard has positions at that offset, and with the program-stressed run's cases as
many as the shard holds) and complete counts for every run: each mode's runs and samples together
make as many checks as `tests/verify.sh` counts in the whole corpus in one mode (each report's
`sources.mode_checks`), and its shards hold `sources.corpus_cases` cases between them; the
`gc-ir` halves together compare `sources.corpus_cases` cases and `sources.syntax_cases` checks
with no difference. It rejects GC suites without both `gc-ir` halves, even in a contract that
omits them. `tests/verify.sh gc-stress` still runs all GC checks locally with one bootstrap;
`gc-ir` runs the two identity halves, `gc-jit` those and the two JIT halves, and `gc-aot` the
three AOT thirds.
The native and opt-off suites run in thirds, Python-free in quarters, and UBSan in fifths
(`tests/verify.sh`'s `shard_cases`). The gate requires each
shard's identity and complete count, and that the shards together make as many checks as an
unsharded suite: the JIT and AOT shards as many as `tests/verify.sh` counts in the whole corpus
(each report's `sources.suite_checks`; opt-off's once per `PYSTACHY_OPT` setting), and the UBSan
fifths, which run in each mode, twice `sources.mode_checks`. Locally, `native` and `opt-off` run
all three of their thirds, `python-free` rebuilds the compiler once and runs its four quarters,
and `ubsan` builds the sanitized compiler once and runs its five fifths.

Every such suite is sharded by `tests/corpus.sh`'s `corpus_shard` (`tools/shard_cases.sh` for the
coverage and variant workflows): the cases are taken heaviest first by their weight in
`tests/case_weights.txt`, each joining the shard whose total weight is least so far, and each
shard lists its cases heaviest first, so that `tests/run.sh`'s workers do not end on a long case.
Every corpus case joins exactly one shard whatever the table holds: a case it lacks weighs its
kind's default, and a stale or malformed entry counts for nothing, so the table can cost balance
but never coverage. Integer weights and the C locale make the shards identical on every runner. A
weight is a case's time in thousandths of a median program's. The suite steps of `native`,
`opt-off` and `ubsan` keep their per-case times (`build/verify/*-times.log`, from
`PYSTACHY_CASE_TIMES`) in each group's artifact; refresh the table from one run's native thirds:

```sh
python3 tools/case_weights.py x86_64-verification-native-0/verify/tests-native-0-times.log \
  x86_64-verification-native-1/verify/tests-native-1-times.log \
  x86_64-verification-native-2/verify/tests-native-2-times.log
```

Use the `aarch64-` artifact prefix for ARM64 timings. Keep architectures in separate
timing series. The table comes from the native halves of CI run 40753601291
(`--keep`; they timed every case), before architecture-prefixed artifact names.
It replaced a first table made from the 2-second file times of the promoting-int sweeps of runs
40719438561 and 40731629369 and a one-core local run of the deviations and rejections. Judged by
that run's opt-off halves and UBSan thirds, which it was not made from, the heaviest shard exceeds
an even split by 0.2% for halves and 0.4% for thirds, against 0.4% and 1.9% with the first table.
The runners vary far more: in that run a `znver3` runner took 1.2-1.4 times as long per case as a
`znver4` one (the native halves took 598 s and 429 s), so a job's time depends mostly on the
runner it lands on. Since a half took 10.0-10.4 minutes on `znver3` runners in that run, native
and opt-off run in thirds. UBSan thirds took 10.85 and 10.87 minutes in CI run 40764559484,
so UBSan was split into four quarters with an independent sanitized rebuild in each CI job.
In [CI run 43263073296](https://github.com/den-run-ai/pystachy/actions/runs/43263073296),
full x86-64 UBSan jobs reached 13m14s and Python-free reached 12m57s. UBSan now uses five
shards and Python-free four, retaining their complete corpus and mode counts. The new placement
still needs repeated CI timing evidence for the headroom target; the 15-minute job limit is unchanged.
The CPython-hosted compiler is checked by identity rather than by executing its output again:
`hosted` requires its IR (`rt` for `rtmode_*` cases, with the IR check on), every message and the
exit status to equal stage 2's for every case (`sources.corpus_cases`), and its `check` results
for every `syntax_*` case (`sources.syntax_cases`; both counted in `tests/corpus.sh`'s corpus), each
comparison in a worker per CPU. The LLVM tools build the same program from the
same IR, and the `native-*` groups run every case's stage-2 output in JIT and AOT, so executing
the hosted compiler's identical output again added no coverage; it replaced three jobs, whose
Verify steps took 24.3 minutes together in run 40719438561 (a historical measurement). A sample
still runs end to end with the hosted compiler, so its driver's `run`, `build` and `check` paths
execute in this job too, as they do in `runtime-cache`, `jit-dead-code`, `unicode-audit`,
`compile-limits` and `scaling`: shard 0 of 64, and the first program in C order of each kind whose
run takes the hosted driver past the IR along a path of its own (`tests/verify.sh`'s
`hosted_strata`): one that sends itself SIGINT, one with `NAME.full`, one with `NAME.in`, one with
`NAME.path`, and one that imports a module named `ffi`. The step reports the sample and the
program of each kind, and fails if a kind has none; the gate requires every kind, each a program
of the checkout's corpus of that kind and in the sample. The maintainer accepted this identity
check with its stratified end-to-end sample on 2026-10-28.

The `unicode-audit` contract also runs `tools/bytescanprobe.c` normally and with GC
stress. Its independent scalar oracle covers all byte values, alignments, tails,
delimiter predicates and range boundaries. Guard pages expose reads outside the
declared range, and deterministic word/scalar counts ensure long spans retain bulk
scanning. Run it independently with `make bytescanprobe`; its timings are not gates.
The same contract runs `tools/floatprobe.c` in both modes: six deterministic
allocation checks and 64 exact-terminator guard-page spans. Suitable ASCII
float strings need no parser temporary; trailing whitespace and underscores
retain bounded copies. Run it independently with `make floatprobe`.
The compiler-scaling check is split by shapes: `scaling-0` checks those of `SCALING_0`, about
half of the lines the CPython-hosted compiler executes, and `scaling-1` every other shape of
`tools/scaling.py` (its `-x`), so a new shape is checked as well; the gate requires the two to
check every shape once. Both run in the `scaling` group with `tools/scaling.py -j`, one shape per
CPU (`PYSTACHY_JOBS` if set): `--check` compares counts, which do not depend on the load, so its
seconds there are informational; measure timings with `-j 1`.
The `contracts` group runs its steps in three phases (`tests/verify.sh`'s `contracts_*` lanes), after
one runtime build per compiler so that each step finds the warm cache it found when the steps ran
one after another: `check-ir` and `rt-abi`, which use every CPU; `compile-limits` beside one lane
only, since its compilers must stay under ten CPU seconds (the hosted one takes about eight on CI,
and a busy sibling thread of CI's two-thread cores would add to that); then four lanes at once.
`contracts_d` runs `aot-dead-code` after `jit-dead-code`; both report through the aggregate gate. A
shell's background job starts with SIGINT and SIGQUIT ignored, so the steps whose programs take
SIGINT (`ffi`, `select-io`) are in the shell's own lane, `contracts_fg`. Each lane keeps its
steps' records and the shell appends them in the plan's order; a lane that ends before a step
reports fails that step (`lane_ended`). `tools/test_verify_contracts.py` checks the order, the
overlap, what runs beside `compile-limits`, the SIGINT disposition and both failures. `runtime-cache` runs `tests/cache.sh` for
the two compilers at once: each run has its own home, LLVM wrappers and temporary directory.
On TERM, or SIGINT as Ctrl-C sends it, `tests/verify.sh` ends every process its background jobs
started (the lanes and the background `tests/cache.sh` run, `stop_jobs`), not their shells alone,
whose programs would run on into `build/verify`; `tools/test_verify_contracts.py` checks that none
survives.
The final report job allows ten minutes for artifact downloads and validation.

The compiler state controls (`python3 -m unittest discover -s tools -p
'test_compiler_state*.py'`) run in Lint. They check declared Frame mappings,
successful dry emission restoration, known restart rewinds and the nested-state
probe's ability to detect entry leaks and failed restoration. The standalone
`tools/compiler_state_nested_probe.py --strict` reports known #822 violations
on the historical baseline; its success is not asserted by the mechanism tests.
These checks cover the listed boundaries, not exhaustive state ownership or safe
retention of every semantic discovery. The hosted dry-call fixture lives in
`tools/fixtures/compiler_state_dry_template.py`; native regressions remain in the
normal differential corpus. Historical investigation and raw evidence are linked
from [PR #818](https://github.com/den-run-ai/pystachy/pull/818).

The runtime-mode controls require `runtime_ir()` to restore the exact entry state
of `MODULES["_rt"]` on success and failure, including an absent entry or an existing
false value. Failures during loader construction, loading and generation exercise
the actual cleanup boundary; removal and incorrect-restoration mutations must fail.
A real compiler-error sequence checks that a failed runtime compilation cannot
make a subsequent ordinary program import the internal `_rt` module.

`tools/compiler_state_globals.py`, also tested by that Lint pattern, inventories
module-level containers under the compiler's declaration conventions. Every
container is classified as a reviewed lookup table, restart-rewound state,
load-reset state, or currently retained state. It rejects unclassified containers and new writers,
including direct writes, imported names, simple local and default-argument aliases,
assignment expressions and nested subscripts. Module subscript aliases retain possible
source owners for later mutation checks without declaring scalar-capable reads as
new containers. Import and alias propagation can retain multiple possible owners
across rebindings; reports require review. Explicit re-export chains preserve those
original owners; qualified
exports expand only to attribute-path depths referenced in the scanned source, so
module-object import cycles remain finite. Container annotations include explicit
builtin/typing import aliases, quoted forms, unions, `Optional` and `Annotated`
wrappers; metadata is not treated as a type. Direct bound and builtin unbound
mutator calls include in-place dunders and reinitialization, with explicit import
resolution and lexical builtin-name shadows. Callable alias/effect inference remains
outside the check. Loop, context, exception and pattern targets, plus named
definitions, participate in global-rebinding and local-shadow checks without
inferring aliases from arbitrary iterators or context managers. The four rewind
classifications are tied to the executable restart controls; removing a rewind must
still fail those controls. `Loader.program()` rebuilds `FILES` and `DYNFILES` together
before parsing each program, including runtime loads and compilation restarts. Hosted
sequence tests cover both dynamic-Any opt-in directions, successful and failed calls,
imports, runtime interleaving and removal of either reset. The main source diagnostic
name remains caller-owned (`diagnostics.SRC`); imported diagnostics use the current
file table. These process-global tables do not provide concurrent compilation isolation.
`diagnostics.CAPTURED` is separately observer-owned retained state: capture is off by
default, and `diagnostics.fail()` is its only compiler writer, appending a terminal
diagnostic after any retry guards. The [inspection tool](compiler-inspection.md)
clears it before each request in a fresh worker process and reads it after compilation
returns or fails. The observer also supplies `CAPTURE` and `PHASE`; neither a loader
reset nor a restart clears its report. The external worker reset is outside this
compiler-source inventory, and does not establish safe in-process session reuse.
The capture tests preserve legacy rejection output, and inspection tests exercise a
failed request followed by a repaired import in another worker. Inventory controls
reject an added capture writer or a stale declaration of the existing writer.
`program_cache` owns state for a CLI cache attempt, retained across inference retries.
`start()` clears its source, import-probe, static input and toolchain-layout snapshots, resets validity
and enables tracking; `stop()` only disables tracking. A conflicting snapshot stays
invalid through every retry. The settled static hash memo and its last-loaded cache
root persist across attempts in the process; hashes can also be loaded from or
published to the private disk memo. The inventory checks direct resets and flag/memo
writers. Snapshot insertion through `_record(table, ...)` is a parameter-mediated
effect outside this scanner; the cache tests cover capture, conflicting retries and
publication. This state does not provide concurrent in-process compilation isolation.
`GLUE` and `SPECSHOW` currently retain discoveries across restarts; the inventory records
that behavior without certifying its safety. This is a hosted drift check, not a
whole-program effect analysis: arbitrary helper calls, object-attribute aliases,
unannotated factory results, and effects inside class bodies, anonymous function
bodies or comprehensions require review. Lambda defaults are scanned in their
defining scope. Method scans include local classes and preserve their enclosing
function aliases. Straightforward class field/import declarations can supply method
defaults, but class fields are not method closure variables; conditional class
initialization and control-flow-sensitive alias retention still require review. One explicit alias exception
covers `gen_verify` borrowing `NOLABELS` as `out`; its copy-before-write control
flow still needs review. The checker has no native
compilation overhead and does not establish that lookup tables are deeply immutable.

The [Lint workflow](../.github/workflows/lint.yml) runs alongside CI: `make check-fast lint`,
report-gate tests and recording checks use the pinned CPython and require no compiler bootstrap.
When Lean validation is selected, Lint builds and audits the pinned checker first;
`make check-fast` then runs all boundary test groups once with missing checkers treated as
errors. Ordinary local `make check-fast` retains its existing optional Lean behavior.
The verification-harness and compiler-state control suites overlap as two isolated
unittest processes. Lint waits for both, prints their logs separately and fails if
either suite fails; the same coverage runs for documentation PRs, main and manual runs.
The coordinator preserves normal SIGINT handling, cancels both process groups and
reaps the suite processes before returning from SIGINT or SIGTERM cancellation.

Generated-user and generated-runtime ASan controls run in the existing x86-64
`safety-1` worker on code PRs and `gc-jit-0` on main pushes and manual runs, using
LLVM 18 and its compiler-rt runtime. All four tests in `tools/test_runtime_asan.py` run there;
every other `test_runtime_*.py` file runs in the second native JIT/variant worker on PRs
and the x86-64 `gc-jit-0` job on full runs. Those controls retain real-driver C-cache
integration, sanitizer setup, and both positive and negative CPU-buffer ownership probes.
They run after each worker's existing checks, with at most the C-cache test's two
concurrent producers. This preserves code verification coverage with the same jobs,
workers and 15-minute timeouts while keeping native controls out of Lint's budget.
Each controls step is required by its job's result and the aggregate gate;
documentation-only PRs use the existing plan that skips native verification.

`make check-repository`, included in `check-fast`, rejects root `research` paths in
the Git index and tests the gate against temporary repositories. It checks tracked
files even when ignored; local untracked experiments are outside the merge gate.
Review still checks for research dumps, transient handoffs and unapplied patches
in other directories; curated reports and maintained tests are allowed.
It also validates every GitHub Actions workflow with actionlint 1.7.12, installed
from its SHA-256-verified release archive. To run the same check locally, install
that [upstream version](https://github.com/rhysd/actionlint/releases/tag/v1.7.12)
and run `actionlint -pyflakes=` from the repository root.
Embedded shell checks remain enabled, using the pinned `shellcheck-py` executable;
Pyflakes integration is disabled, so embedded Python snippets are not linted here.
Ruff checks the repository's Python files separately.

The same Lint job builds and audits the optional
[Lean payload-guard prototype](../tools/lean_boundary/README.md) on every main push
and manual dispatch. For PRs, it checks the cumulative merge diff for changes to
the prototype, compiler, inspection exporter, boundary tests, Makefile, Lint workflow or
Python/development dependency pins. Missing merge history runs the check;
documentation-only PRs skip it. The selector has temporary-Git-history controls.
It builds the checker with pinned Lean 4.35.0, then runs the kernel, adapter and negative
controls once through `make check-fast`, requiring the checker. No extra PR job is added.
Lint and verification cache only the pinned release archive. `tools/setup_lean.py` checks
its SHA-256 on every restore, downloads a verified replacement for a missing or corrupt
archive, and extracts a fresh toolchain. Compiled checkers and proof results are not cached.

Complete Lean corpus sweeps run on main and manual CI. The x86-64 `gc-jit-1` group runs
`make check-lean-corpus`: the corpus tool's tests
(`tools/test_lean_corpus.py`), then each dynamic-`Any` test program compiled by
the hosted compiler, failing unless Lean proves every dynamic payload read guarded
and every [unchecked list read and dict entry](../tools/lean_boundary/ACCESS.md) in
bounds and live, followed by `make check-lean-int` for promoting-integer
[fit claims](../tools/lean_boundary/INT.md). Reports are uploaded as
`lean-corpus.json` and `lean-int.json`. Full-run x86 `scaling`
runs `make check-lean-storage` for [storage guards](../tools/lean_boundary/STORAGE.md),
including programs that import opted-in modules, and upload `lean-storage.json`.
Code PRs and full CI retain `make check-lean-guards` in the x86 `contracts` group on the explicit
`null_guards.py` and `union_guards.py` examples, uploading
`lean-guards.json`. The selection and its limits are recorded in
[GUARDS.md](../tools/lean_boundary/GUARDS.md). These enforce bounded null/union guard
coverage; the strict full-corpus guard command remains an investigation tool with
unsupported forms, not a passing whole-corpus gate. Arithmetic reports separately
count actual checked overflow reconstructions and other observed arithmetic.
All sweeps use two local processes within existing jobs and their 15-minute limits.
On full runs, the corpus and integer proofs start after `gc-jit-1` finishes;
runtime-cache and program-cache probes retain their own job. This keeps those
cache checks from sharing a time budget with the complete Lean corpora.
Lint runs none of these corpora. The bridge's Python tests also run in
`make check-fast`; they skip executable checks when Lean has not been built.
The dedicated target requires executable checks and fails if the executable
is missing. Lean is a development-only dependency for this bounded prototype.

`make typecheck` uses the mypy version pinned in `tools/requirements-dev.txt` and
the scope in [`mypy.ini`](../mypy.ini): `pystachy.py` and all of `src/`, targeting
the supported Python 3.11 bootstrap floor. It checks annotated arguments, returns,
record fields and local values, including bodies without complete annotations.
Unannotated locals may change type across control-flow paths. Reused annotated
locals have one declaration per function. There are no whole-module ignores or
disabled error categories; the one local argument exception documents a terminating
call through an untyped receiver and is checked for obsolescence.

This is an incremental check, not strict typing: the generic `gen_*` operations
intentionally leave `self` unannotated for self-hosted specialization, so accesses
through that receiver remain unchecked. Keep the one-way component dependencies
described in [`src/README.md`](../src/README.md); do not add runtime imports of `Gen`
just for mypy. The initial gate excludes development tools, vendored/ported modules,
test programs (many intentionally invalid), and `runtime.py`'s compiler-only `_rt`
intrinsics. It does not replace bootstrap, IR parity or runtime verification.

On `main` and manual dispatch, the [Installation workflow](../.github/workflows/install.yml)
builds on Ubuntu x86-64/ARM64 and macOS ARM64/x86-64, then runs hosted/native JIT/AOT
installation smoke (`tools/install_smoke.py`). Both Linux smoke jobs and the macOS
ARM64 smoke job also check the optional [netio bridge](../examples/netio/README.md)
with the freshly built compiler. All twelve
socket/readiness scenarios and the completion-order pipe drain run against
CPython's stdlib oracle in native JIT/AOT and both GC-stress modes. Linux also
runs the same scenarios with the hosted compiler, every netio harness test,
the CPython smoke benchmark, and the standalone C ownership probe with ASan,
UBSan and leak detection. These Linux checks run in Installation
rather than Lint so Lint retains its 15-minute bound. Netio probe steps have a
five-minute limit and retain JSON reports for seven days, including failed or
incomplete runs; only reports with `result: pass` and all expected modes
establish successful validation. The three primary platforms also install the
compiler with pip and uv from the exact GitHub commit and verify JIT/AOT outside the checkout
(`tools/compiler_install_smoke.py`). The [Packages workflow](../.github/workflows/packages.yml)
builds the example and ports source wheels and runs them under CPython, JIT and AOT
(`tools/package_smoke.py`) on `main` and manual dispatch. Full CI's separate qualification
job runs release unit tests and native archive smoke after the O1 bootstrap comparison,
using the original verified O2 compiler for the archive. Distribution checks stay outside
PRs; both Linux architectures retain full FFI, stack, ABI, JIT-runner and cache coverage
in the main/manual verification matrix. The
[Release workflow](../.github/workflows/release.yml) reserves its full archive/container matrix
for tags and release dispatch; publishing requires CI, Installation, Lint and Packages on the exact release commit
([releases](releasing.md)).

The [Coverage workflow](../.github/workflows/coverage.yml) runs apart from PR CI, daily, manually
and on relevant `main` pushes; no check requires it; [reading coverage](#reading-coverage) describes it. So
does the [Variants workflow](../.github/workflows/variants.yml), which
[configuration variants](#configuration-variants) describes.

Every job, including release jobs, has a time limit of at most 15 minutes. Release preparation
waits at most ten minutes for its exact-commit CI evidence. Expensive new checks must fit the
existing PR budget or run in the full matrix; keep the job and time ceilings unchanged.

Lint also runs the optional [communication buffer/completion probe](../examples/comm/README.md)
with the hosted compiler, JIT/AOT, GC stress and a sanitized standalone C probe.

Contributions use the [contribution-rights policy](../CONTRIBUTING.md#contribution-rights)
without DCO certification. The existing submission bot sends a one-time,
non-blocking rights/guidelines/AI acknowledgment reminder on new PRs. The legacy
DCO workflow always skips; remove it after deleting its required status in
GitHub branch protection settings.
