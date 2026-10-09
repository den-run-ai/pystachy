# Testing and verification

Pystachy's promise, that a compiled program prints what CPython prints, is checked by running
the same programs under both and comparing the results. This page describes the test suite,
the full verification run that CI performs on every push, and the tools that keep refactors
honest.

| command | what it checks |
|---|---|
| `make` | the bootstrap: the compiler built by itself reproduces its own LLVM IR byte for byte |
| `make test` | the differential tests with the native compiler, JIT and AOT |
| `make test-py` | the same tests with the compiler running on CPython |
| `make verify` | the bootstrap, both test runs and the other steps under [make verify](#make-verify), with a JSON report in `build/verification.json` |
| `make irsame REF=<commit>` | a refactor changes no program's IR, message or exit status |
| `make check-ir` | `llvm-as` accepts the IR of every program in the corpus |

## Differential tests

`tests/run.sh` runs every `tests/*.py` twice — JIT and AOT — and compares stdout plus exit
status with what CPython recorded in `tests/*.out` (stdin from `tests/*.in`), and the last
stderr line with `tests/*.err` where CPython wrote to stderr. `tests/record.sh NAME`
records a test's expected output from CPython, the way `tests/run.sh` runs it. Each `tests/errors/*.py`
must be rejected with the message on its first line (a `tests/errors/syntax_*.py` one also by
`pystachy check`), and each `tests/deviations/*.py` must print its hand-written expected
output. Where `tests/NAME.path` exists, it is the module path: `PYTHONPATH` when
`tests/record.sh` records the test, `PYSTACHY_PATH` when `tests/run.sh` runs it. The cases run
in `PYSTACHY_JOBS` workers at once (default: one per CPU). The programs cover arithmetic and overflow edges,
strings, escapes and f-strings, a 400-case sample of the format-spec language, lists,
dicts (also keys that collide in the hash table), tuples, classes, dataclasses, `Optional` structures, rich comparisons, defaults,
imports, modules and packages (`tests/mods/`, `tests/scope/`, `tests/infer/`), what the
loader decides at import time (`tests/loader/`), a program run through a symbolic link
(`tests/linked/`), CPython's syntax errors and its compiler's block, parser-stack and marshal limits, templates, empty containers typed by their first
use, loops with `else`, the `lib/` modules (`tests/lib_*.py`), definite assignment, sorting
(timsort's exact comparisons), loops that change what they iterate, files and the standard
streams, exceptions and exit statuses, runtime errors, garbage-collector churn, classic
algorithms, a small interpreter, and 16 programs from Ouro v2. Where `tests/NAME.full`
exists, the program's stdout is `/dev/full`. Current result: **1175 passed, 0 failed** with
both the CPython-hosted and the self-compiled compiler.

## `make verify`

`make verify` (`tests/verify.sh`) runs the whole verification and writes
`build/verification.json` with each step's result, duration and counts, the toolchain
versions, platform, git commit and a timestamp:

- **bootstrap** — stage1, stage2 and stage3 emit identical IR;
- **tests-cpython / tests-native** — the differential tests with each compiler, JIT and AOT;
- **python-free** — `PATH` holds only the LLVM tools, the system linker and a few POSIX
  tools (`python3` is checked to be unreachable); the native compiler rebuilds its runtime
  and itself, reproduces the IR and passes the tests;
- **ubsan** — the runtime and every test program built with
  `-fsanitize=undefined -fno-sanitize-recover=all` must still match CPython;
- **check-ir** — `llvm-as` accepts the IR of every program of the corpus below;
- **gc-stress** — the native compiler, collecting every 100 allocations, reproduces the IR,
  and every test passes JIT and AOT with a collection at every allocation
  (`PYSTACHY_GC_STRESS=1`);
- **benchmarks** — output equal to CPython's, with timings;
- **dict-probes** — `tools/dictprobe.c` counts the table slots that dict insertions and
  lookups visit for twelve key patterns that defeat a weak hash or probe sequence (`i << 46`,
  spaced ints, str keys sharing a long prefix or suffix, ...) and every shift `i << s`, with
  sequential keys as the control, at 4k to 30k keys, and fails above 3 slots per lookup: the
  counts are the same on every machine, so no timing is compared with a threshold;
- **scaling** — `tools/scaling.py --check` compiles generated programs of 500 and 1,000
  functions, globals, classes, modules, chained imports, `while True` breaks, `elif`s and
  comprehensions with both compilers; the lines the CPython-hosted compiler executes, and the
  items its builtin calls copy or scan, must grow no faster than the programs.

## IR identity for refactors

`tools/irsame.sh OLD NEW` checks that a refactor of the code generator changes nothing: both
compilers run `ir` over the corpus (`pystachy.py`, `tests/*.py`, `tests/deviations/*.py`,
`bench/*.py` and `tests/ir/*.py`) and must emit the same IR byte for byte, and for each
`tests/errors/*.py` the same messages and exit status. `make irsame REF=<commit>` (default
`HEAD`) builds that commit's compiler in `build/ref/`, cached by commit, and compares it with
`./pystachy`; `make irsame-py` compares the CPython-hosted compilers. `make check-ir` runs
`llvm-as` on the IR of every program of the corpus. `tests/ir/*.py` probe code-generation
paths the other programs never take (dead code after `return`, templates instantiated during
a look-ahead, nested templates, guards repeated in one function): these two tools compile
them, but they never run. Both
need only POSIX sh, run in `PYSTACHY_JOBS` workers, and take a few seconds.

## Syntax errors against CPython

`tools/syntax_sweep.py` compares the syntax errors `pystachy check` reports with CPython's
`compile()`: over CPython 3.13's standard library and the installed packages (5,701 files)
the two agree everywhere except 19 valid files Pystachy cannot parse (tabs in indentation,
`\N{...}` escapes, an f-string field that reuses its quote).

## Continuous integration

`.github/workflows/ci.yml`
runs `make verify` on every push and pull request (ubuntu-24.04, LLVM 18 from apt,
Python 3.13) and uploads the report as an artifact.
