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
| `make verify` | Run the complete verification plan and write `build/verification.json`. |
| `make lint` | Run Ruff, ShellCheck and Clang warnings. |
| `make check-recordings` | Check expected outputs, remaining deviations, unchanged upstream sources and test-tree hygiene. |
| `make test-cache` | Check runtime build-cache reuse, invalidation and failed-build handling with both compilers. |
| `make test-ffi` | Check C calls, FFI diagnostics and CPython extension modules. |
| `make check-ir` | Check the typed IR and its LLVM lowering across the compiler corpus. |
| `make check-runtime` | Check runtime declarations, effects and source agreement. |
| `make irsame REF=<commit>` | Compare IR, diagnostics and exit status with a reference compiler for a refactor. |
| `make bench-extended-check` | Check the extended benchmark runner and CPython/JIT/AOT checksums; no timing thresholds. |

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
| Libraries and interoperability | Regex differential fuzzing and deterministic matcher budgets; FFI calls and extension modules; runtime build-cache rules. |
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

`make check-ir` verifies typed-IR structure, LLVM acceptance, and the effect summaries or
runtime calls recorded for `tests/ir/*.py`. These probes compile without running;
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

## Continuous integration

The [CI workflow](../.github/workflows/ci.yml) runs on pull requests (including forks), pushes
to `main` and manual dispatch. Pull requests test the branch merged with the then-current
`main`. A newer PR push cancels its previous run; commits on `main` run to completion.
The toolchain is Ubuntu 24.04, LLVM 18 and the CPython version pinned in `.python-version`.

Seven groups run in parallel, each with its own fixed-point bootstrap and 15-minute job limit:

| Group | Work after bootstrap |
|---|---|
| `hosted` | CPython-hosted differential suite. |
| `native` | Native suite and optimization-off suite. |
| `python-free` | Rebuild and run with no Python on `PATH`. |
| `ubsan` | Sanitized compiler/runtime and JIT/AOT suite. |
| `gc-stress` | Collector-stressed self-compilation and suite, overlapped within the job. |
| `contracts` | Runtime, IR, library and resource-bound checks. |
| `benchmarks` | Benchmark correctness/timings and compiler scaling; extended correctness checks reuse the verified compiler. |

A failed group leaves the others running. The required check remains
`make verify (Linux x86-64, LLVM 18, Python 3.13)`. Its report gate requires every group to
succeed and rejects missing/unexpected stages, inconsistent source revisions/hashes or
toolchains, and different bootstrap IR. Reports and logs are uploaded as workflow artifacts.

The combined report's duration is the longest group's verification work;
`ci.runner_seconds` measures aggregate work. Queueing, setup and other steps add to elapsed
workflow time. The 15-minute limit applies to each verification job.

The [Lint workflow](../.github/workflows/lint.yml) runs alongside CI: lint, report-gate tests
and recording checks use the pinned CPython and require no compiler bootstrap.
