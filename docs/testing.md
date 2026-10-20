# Testing and verification

Supported programs are checked against CPython in both JIT and AOT modes. The suite also
checks rejected programs, documented deviations, the self-hosting fixed point and runtime
contracts. Use the CPython version in `.python-version` and install the development tools
with `python3 -m pip install -r tools/requirements-dev.txt`.

## Commands

Run these from the repository root:

| Command | Purpose |
|---|---|
| `make` | Bootstrap the native compiler; successive compilers must emit byte-identical IR for the compiler and subset runtime. |
| `make test` | Run the differential, rejection and deviation suite with the native compiler, JIT and AOT. |
| `make test-py` | Run the same suite with the compiler hosted by CPython. |
| `make coverage` | Measure which statements and branches of the compiler's source that suite, the FFI and runtime-cache suites, the IR checks and the compiler's unit tests run, in the CPython-hosted compiler ([compiler coverage](#compiler-coverage)). |
| `make runtime-coverage` | Measure which lines and branches of the runtime's C code the corpus's programs and the FFI suite run ([native runtime coverage](#native-runtime-coverage)). |
| `make verify` | Run the complete verification plan and write `build/verification.json`. |
| `make lint` | Run Ruff, ShellCheck and Clang warnings. |
| `make check-recordings` | Check expected outputs, remaining deviations, unchanged upstream sources and test-tree hygiene. |
| `make test-cache` | Check runtime build-cache reuse, invalidation and failed-build handling with both compilers. |
| `make test-ffi` | Check C calls, FFI diagnostics, embedded CPython (`pyobj`) and CPython extension modules. |
| `make check-ir` | Check the typed IR and its LLVM lowering across the compiler corpus. |
| `make check-runtime` | Check runtime declarations, effects and source agreement. |
| `make irsame REF=<commit>` | Compare IR, diagnostics and exit status with a reference compiler for a refactor. |
| `make bench-extended-check` | Check the extended benchmark runner and CPython/JIT/AOT checksums; no timing thresholds. |
| `make bench-pyperformance-check` | Check the pyperformance runner and the ported benchmarks' CPython/JIT/AOT output; no timing thresholds. |
| `make blas-check` | Check the optional `cblas_dgemm` adapter (`examples/ndarray`) against NumPy and nanoGPT's BLAS backend against its scalar one, under CPython, JIT, AOT and GC stress; needs an LP64 `libblas.so.3` and NumPy. `LD_LIBRARY_PATH` selects the provider; CI checks OpenBLAS and the reference BLAS. |

For a focused edit, select the affected cases:

```sh
make test FILES="tests/str_*.py tests/errors/rtmode_*.py"
make test-py FILES="tests/str_*.py tests/errors/rtmode_*.py"
tests/run.sh ./pystachy jit tests/lib_fnmatch.py
```

`PYSTACHY_JOBS` controls test workers; the default is one per CPU. Full verification retains
all coverage even when CI distributes the work across jobs.

## Differential tests

`tests/run.sh` compares these results for each `tests/NAME.py`:

| Artifact | Contract |
|---|---|
| `NAME.out` | Exact stdout followed by `[exit N]`, recorded from CPython. |
| `NAME.err`, when present | The final stderr line must match CPython's. Without this file, stderr must be empty. |
| `NAME.in`, when present | Input supplied to the program. |
| `NAME.path`, when present | Module path: `PYTHONPATH` for the recording, `PYSTACHY_PATH` for the compiled test. |
| `NAME.full`, when present | Send stdout to `/dev/full` to check failed writes. |

An AOT build's diagnostics are kept separate from the program's stderr and must be empty.
The runner enables `PYSTACHY_IRCHECK=1` unless explicitly overridden.

`tests/errors/*.py` must fail with status 1 and one source diagnostic on stderr:
`FILE:LINE: error: MESSAGE`, containing the expected message from the source's first line.
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

| Area | Checks |
|---|---|
| Compiler and IR | Valid typed/LLVM IR, runtime ABI and effects, bounded specialization failures, linear compilation and inherited-AST storage, JIT dead-code removal and inlining. |
| Runtime | CPython comparisons for subset runtime functions; dictionary probes and string-hash caching; list storage, shared-container comparisons, file-buffer accounting and streaming consumers. |
| Libraries and interoperability | Regex differential fuzzing and deterministic matcher budgets; FFI calls, embedded CPython and extension modules; runtime build-cache rules. |
| Benchmarks | CPython-equivalent output plus advisory timings. |

The implementation and exact budgets live in `tests/verify.sh` and its named `tools/` probes.
Useful individual checks include `make re-fuzz`, `make re-probe`, `make dictprobe`,
`make listprobe`, `make eqprobe`, `make fileprobe`, `make streamprobe` and `make jitprobe`.
They use deterministic operation or allocation limits where possible; shared CI runners do
not gate on benchmark speed.

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

The oracle compares emitted IR byte for byte, and rejection messages and exit statuses.
Use it when a refactor should preserve code generation. An intentional optimization can
change IR and needs behavioral tests instead.

`make check-ir` verifies typed-IR structure, LLVM acceptance, and the effect summaries,
runtime calls, function attributes or field TBAA tags recorded for `tests/ir/*.py` (`NAME.fx`,
`NAME.calls`, `NAME.attrs`, `NAME.tbaa`). These probes compile without running;
`tests/ir/pending/` holds probes for open bugs.

## Syntax errors against CPython

`tools/syntax_sweep.py` compares `pystachy check` with CPython's `compile()` without running
the sources. Give it files, directories or snippet files separated by `----` lines:

```sh
python3 -I tools/syntax_sweep.py --compiler ./pystachy /usr/lib/python3.13
```

It reports diagnostic differences separately from valid Python that Pystachy cannot parse.
Current boundaries are in [syntax checks](language/semantics.md#syntax-errors). Earlier test
counts and syntax-survey results are retained as [historical snapshots](archive/verification-snapshots.md).

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
| `unit` | The compiler's unit tests, `tools/test_typed*.py` and `tools/test_function_summaries.py`. |
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
run the same compiler code.

[`.coveragerc`](../.coveragerc) holds the settings. Each compiler process starts through a
launcher that counts it and writes its own data file. `pystachy run` replaces its process with
`lli` through `os.execv`, so coverage.py saves the data first (`patch = execv`); without that,
JIT runs record nothing. A suite fails unless every process left data, but for the one build
that `tests/cache.sh` kills on purpose. `tests/cache.sh` runs a copy of the compiler in a
directory of its own, which `[paths]` maps to `src/`. Each suite starts with an empty runtime
cache, so the runtime's build is measured too. `make coverage` fails when a test fails or data
is missing, never because of a percentage: there is no threshold.

`COVERAGE_SHARD=I/N` limits the corpus to the cases `I`, `I + N`, `I + 2N`... in the order of
`tests/verify.sh`'s shards, and `COVERAGE_REPORT=0` leaves out the report.
`tools/coverage_report.py` combines such parts later. It first checks that every part passed
with complete data, that no suite was measured twice, that no shard is missing and that all
parts measured one commit.

## Native runtime coverage

`make runtime-coverage` measures which lines and branches of the runtime's C code the programs
run: `runtime.c` with the `ryu/` files it includes, `pyembed.c` (embedded CPython) and `pyext.c`
(the extension-module ABI). It builds a new runtime cache with clang's
[source-based coverage](https://clang.llvm.org/docs/SourceBasedCodeCoverage.html)
(`PYSTACHY_CFLAGS="-fprofile-instr-generate -fcoverage-mapping"`), then runs the corpus's
programs, JIT and AOT, and the FFI suite, AOT, with the native compiler. It needs clang's
profile runtime (Ubuntu's `libclang-rt-18-dev`, which `tools/setup.sh` installs) and LLVM's
`llvm-profdata` and `llvm-cov`. `FILES="..."` selects corpus cases. The results go to
`build/runtime-coverage/`: `html/` (llvm-cov's annotated source, with branch counts),
`summary.md` (lines, branches, functions and regions for each file and for each section of
`runtime.c`: the collector, strings, arithmetic, lists, dicts, sets, I/O, exceptions and the
rest), `coverage.json` (llvm-cov's summary), `lcov.info`, `badge.json` and the suites' logs.

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

The [Coverage workflow](../.github/workflows/coverage.yml) runs both measurements daily and on
demand, and on pull requests and pushes to `main` that change its setup or the suites' runners.
The compiler's coverage runs in four parallel jobs (the corpus in three shards; the FFI,
runtime-cache, unit and IR suites in the fourth) and a fifth combines them; the runtime's runs
in a job of its own, which bootstraps the native compiler first. Job summaries show the summaries, and
the reports are workflow artifacts. After each run on `main`, a separate job, which runs no
tests, commits the summaries and badges of the reports that passed to the `badges` branch, which
the README's badges read:
[`coverage.md`](https://github.com/den-run-ai/pystachy/blob/badges/coverage.md) and
`coverage.json`,
[`runtime-coverage.md`](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)
and `runtime-coverage.json`.

## Continuous integration

The [CI workflow](../.github/workflows/ci.yml) runs on pull requests (including forks), pushes
to `main` and manual dispatch. Pull requests test the branch merged with the then-current
`main`. A newer PR push cancels its previous run; commits on `main` run to completion.
A pull request that changes only Markdown files or `docs/` skips the CI, Installation and
Packages workflows; Lint and the DCO check still run, and pushes to `main` run the full matrix.
The toolchain is Ubuntu 24.04, LLVM 18 and the CPython version pinned in `.python-version`.

A bootstrap job checks compiler and runtime IR fixed points once, then twenty-three groups
run in parallel using its verified compiler. Each group checks the same-run bundle's file hashes,
complete tracked source identity, commit and toolchain before using it. No runtime cache is
shared; Python-free and sanitizer rebuilds, GC stress and cache invalidation checks remain
independent. Local `make verify` and group runs still build their own bootstrap.
The target is under ten minutes of work per group; the 15-minute job limit leaves room for
runner variation:

| Group | Work after bootstrap |
|---|---|
| `hosted-0`, `hosted-1`, `hosted-2` | Three disjoint thirds of the CPython-hosted differential suite, JIT and AOT. |
| `native-0`, `native-1` | Two disjoint halves of the native differential suite, JIT and AOT. |
| `opt-off-0`, `opt-off-1` | Two disjoint halves of the native suite with IR optimizations disabled. |
| `python-free-0`, `python-free-1`, `python-free-2` | Rebuild with no Python on `PATH`; three disjoint thirds of the suite with that compiler. |
| `ubsan-0`, `ubsan-1`, `ubsan-2` | Sanitized compiler/runtime; three disjoint thirds of the JIT/AOT suite. |
| `gc-self` | Collector-stressed self-compilation and identical-IR check. |
| `gc-jit-0`, `gc-jit-1` | Two disjoint halves of the full JIT suite, with compiler and program GC stress. |
| `gc-aot-0`, `gc-aot-1`, `gc-aot-2` | Three disjoint thirds of the full AOT suite, with compiler and program GC stress. |
| `runtime-cache` | The cached runtime's rules with both compilers. |
| `contracts` | Runtime, IR, library and resource-bound checks. |
| `benchmarks` | Benchmark correctness/timings and half of the compiler-scaling shapes; extended correctness checks reuse the verified compiler. |
| `scaling-1` | The other compiler-scaling shapes. |

A failed group leaves the others running. The required check remains
`make verify (Linux x86-64, LLVM 18, Python 3.13)`. Its report gate requires every group to
succeed and rejects missing/unexpected stages, inconsistent source revisions/hashes or
toolchains, different bootstrap IR, and missing or inconsistent bootstrap provenance.
Reports and logs are uploaded as workflow artifacts. A failed producer blocks its consumers
and fails the final gate; there is no fallback to an older compiler.

The combined report's duration is bootstrap work plus the longest consumer group's verification work;
`ci.runner_seconds` measures aggregate work. Queueing, setup and other steps add to elapsed
workflow time. The 15-minute limit applies to each verification job.

GC self-compilation collects every 5,000 allocations and has a separate ten-minute bound.
At the former interval of 1,000, it spent 23 minutes on 15,543 full-heap collections;
the wider interval still exercises thousands of collections without dominating CI.
The GC test suite keeps its compiler interval of 1,000 and collects at **every program
allocation**. Both self-compilation IR identity and full suite counts remain required.
Self-compilation, the two JIT halves and the three AOT thirds use separate runners and report
their own durations. The JIT halves take every other file in a fixed order and the AOT thirds
every third; the halves together, like the thirds, run the full corpus, including rejection and
syntax checks. The final gate requires all six groups, both execution modes, the stress
intervals, distinct shard identities and complete counts for every job: the JIT halves and the
AOT thirds each make as many checks as `tests/verify.sh` counts in the whole corpus in one mode
(each report's `sources.mode_checks`). `tests/verify.sh gc-stress` still runs all GC checks
locally with one bootstrap; `gc-jit` runs the two JIT halves and `gc-aot` the three AOT thirds.
The native and opt-off suites are split the same way, in halves, and the CPython-hosted,
python-free and UBSan suites in thirds (`tests/verify.sh`'s `shard_cases`). The gate requires each
shard's identity and complete count, and that the shards together make as many checks as an
unsharded suite: the JIT and AOT shards as many as `tests/verify.sh` counts in the whole corpus
(each report's `sources.suite_checks`; opt-off's once per `PYSTACHY_OPT` setting), and the UBSan
thirds, which run in each mode, twice `sources.mode_checks`. Locally, `native` and `opt-off` run
both of their halves and `hosted` its three thirds, `python-free` rebuilds the compiler once and
runs its three thirds, and `ubsan` builds the sanitized compiler once and runs its three thirds.
The compiler-scaling check is split by shapes: `scaling-0` (in `benchmarks`) checks those of
`SCALING_0`, about half of the lines the CPython-hosted compiler executes, and `scaling-1` every
other shape of `tools/scaling.py` (its `-x`), so a new shape is checked as well; the gate requires
the two to check every shape once. Locally, `scaling` runs both.
The final report job allows ten minutes for artifact downloads and validation.

The [Lint workflow](../.github/workflows/lint.yml) runs alongside CI: lint, report-gate tests
and recording checks use the pinned CPython and require no compiler bootstrap.

The [Coverage workflow](../.github/workflows/coverage.yml) runs apart from CI, daily and when its
setup changes, and no check requires it; [reading coverage](#reading-coverage) describes it.

The [DCO workflow](../.github/workflows/dco.yml) checks that the author of a pull request from a
fork is listed in `.github/dco-signers.txt`, on main or in the pull request; pull requests from
the repository's own branches skip it. It runs main's copy of the workflow and of
`tools/dco_check.py`, so a change to either takes effect once merged. The
[contributor guide](../CONTRIBUTING.md#rights-and-sign-off) states the rule.
