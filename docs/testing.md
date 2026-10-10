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
| `make check-ir` | every program in the corpus compiles, and the compiler's IR check and `llvm-as` accept its IR |
| `make check-runtime` | the compiler's `RUNTIME` table agrees with `runtime.c` |
| `make lint` | `ruff check` (findings only, `ruff.toml`), `shellcheck` of the scripts as POSIX sh, and clang's warnings on the C sources; `pip install -r tools/requirements-dev.txt` gives the versions that CI's Lint workflow (`.github/workflows/lint.yml`) runs on every push |

## Differential tests

`tests/run.sh` runs every `tests/*.py` twice — JIT and AOT — and compares stdout plus exit
status with what CPython recorded in `tests/*.out` (stdin from `tests/*.in`), and the last
stderr line with `tests/*.err` where CPython wrote to stderr. `tests/record.sh NAME`
records a test's expected output from CPython, the way `tests/run.sh` runs it. Each `tests/errors/*.py`
must be rejected with the message on its first line (a `tests/errors/syntax_*.py` one also by
`pystachy check`), and each `tests/deviations/*.py` must print its hand-written expected
output. Where `tests/NAME.path` exists, it is the module path: `PYTHONPATH` when
`tests/record.sh` records the test, `PYSTACHY_PATH` when `tests/run.sh` runs it. The cases run
in `PYSTACHY_JOBS` workers at once (default: one per CPU), with `PYSTACHY_IRCHECK=1`: the
compiler then checks the IR it built before lowering it (every op is known, each block ends
with its one terminator, an op left as LLVM text is no call, phi or terminator, each op
defines the numbers its lowering prints, branches go to blocks of the function, a phi's
predecessors branch to it, only unwind edges reach a landing pad, and inside a `try` no call
that may raise is left without one). The optimizations that run on the IR before it is lowered
([`docs/typed-ir.md`](typed-ir.md) §7.1) can be turned off for a differential run: `PYSTACHY_OPT=-listget`
(a for loop's reads of the list it steps through, without a bounds check) or `-dictfuse` (one
hash lookup for `if k in d: d[k] += 1` and the like), comma-separated, or `-all`; the tests
pass with each one off. The programs cover arithmetic and overflow edges,
strings (also their Unicode whitespace), escapes and f-strings, a 400-case sample of the
format-spec language, lists, dicts (also keys that collide in the hash table, and tuple keys), tuples, classes
(also their container protocol, static and class methods, and class variables), dataclasses, NamedTuples, typing's forms (`collections.abc`, `Final`, `@overload`, `TypeVar`,
`os.PathLike`), `Optional` structures, optional values (also boxed numbers) and
their narrowing (with CPython's error for each use of `None` where only a value works), rich comparisons, defaults,
imports, modules and packages (`tests/mods/`, `tests/scope/`, `tests/infer/`), what the
loader decides at import time (`tests/loader/`), a program run through a symbolic link
(`tests/linked/`), CPython's syntax errors and its compiler's block, parser-stack and marshal limits, templates, empty containers typed by their first
use, loops with `else`, the `lib/` modules (`tests/lib_*.py`), definite assignment, sorting
(timsort's exact comparisons), loops that change what they iterate, files and the standard
streams, exceptions and exit statuses, runtime errors (also CPython's wording of the type and argument errors Pystachy reports
when it compiles), garbage-collector churn, classic
algorithms, a small interpreter, and 16 programs from Ouro v2. Where `tests/NAME.full`
exists, the program's stdout is `/dev/full`. Current result: **1886 passed, 0 failed** with
both the CPython-hosted and the self-compiled compiler.

## `make verify`

`make verify` (`tests/verify.sh`) runs the whole verification and writes
`build/verification.json` with each step's result, duration and counts, the toolchain
versions, platform, git commit and a timestamp:

- **bootstrap** — stage1, stage2 and stage3 emit identical IR, for the compiler and for `runtime.py`;
- **tests-cpython / tests-native** — the differential tests with each compiler, JIT and AOT;
- **tests-opt-off** — the differential tests with the native compiler and every optimization
  on the IR turned off (`PYSTACHY_OPT=-all`): the passes change no output;
- **python-free** — `PATH` holds only the LLVM tools, the system linker and a few POSIX
  tools (`python3` is checked to be unreachable); the native compiler rebuilds its runtime
  and itself, reproduces the IR and passes the tests;
- **ubsan** — the runtime and every test program built with
  `-fsanitize=undefined -fno-sanitize-recover=all` must still match CPython;
- **check-ir** — every program of the corpus below compiles, and the compiler's IR check
  (`PYSTACHY_IRCHECK=1`) and `llvm-as` accept its IR, and `runtime.py`'s, compiled as the
  runtime is (`pystachy rt`);
- **runtime-table** — `tools/check_runtime.py` (`make check-runtime`) checks the compiler's
  `RUNTIME` table, from which it declares every runtime function, against `runtime.c`: each
  entry's declaration has the types clang compiles the function to, every runtime function
  the compiler names has an entry, and an entry's effect letters are known ones and include
  what the function's C call graph shows (it may raise, allocate, call user code, read the
  lists and dicts of a value it walks by its descriptor, read or write the list, dict or file
  it is passed, use the runtime's state or the C library's I/O, or never return). A function
  that `runtime.py` defines is checked from the IR the compiler builds for it: its definition's
  types, and the effects its code shows (R where a raise survives `opt -O2` in the linked
  runtime, but for the subset's index and divisor checks, and then it must not be `nounwind`
  there, so that a raise in it unwinds to a program's handler); and no function of
  `runtime.py` may reach itself through an operation's lowering or through runtime.c, a
  recursion that nothing in its source would show;
- **gc-stress** — the native compiler, collecting every 1,000 allocations, reproduces the IR,
  and every test passes JIT and AOT with a collection at every allocation of the program
  (`PYSTACHY_GC_STRESS_PROGRAM=1`), compiled by the compiler collecting every 1,000 (at every
  100, the compiler's collections, which mark the IR it keeps until the program is built, would
  take minutes);
- **benchmarks** — output equal to CPython's, with timings;
- **rtcheck** — `tools/rtcheck.py` runs `runtime.py` on CPython and compares each of its
  functions with CPython's str methods, `math` functions and `format()` (and the dict hashes
  with their formulas) on random inputs, about 275,000 cases;
- **rt-abi** — `tools/rtabi.py`: every function `runtime.py` defines or declares has one LLVM
  signature in `runtime.py`, in runtime.c and in every program of the corpus (`llvm-link`
  would accept a mismatch silently);
- **dict-probes** — `tools/dictprobe.c` counts the table slots that dict insertions and
  lookups visit for twelve key patterns that defeat a weak hash or probe sequence (`i << 46`,
  spaced ints, str keys sharing a long prefix or suffix, ...) and every shift `i << s`, with
  sequential keys as the control, at 4k to 30k keys, and fails above 3 slots per lookup: the
  counts are the same on every machine, so no timing is compared with a threshold;
- **scaling** — `tools/scaling.py --check` compiles generated programs of 500 and 1,000
  functions, globals, classes, modules, chained imports, `while True` breaks, `elif`s,
  comprehensions, links of a dict key's chain of values, dict lookups and global dicts with
  both compilers; the lines the CPython-hosted compiler executes, and the items its builtin
  calls copy or scan, must grow no faster than the programs.

## IR identity for refactors

`tools/irsame.sh OLD NEW` checks that a refactor of the code generator changes nothing: both
compilers run `ir` over the corpus (`pystachy.py`, `tests/*.py`, `tests/deviations/*.py`,
`bench/*.py` and `tests/ir/*.py`) and must emit the same IR byte for byte, and for each
`tests/errors/*.py` the same messages and exit status; when both have runtime mode, they
compile `runtime.py` and `tests/errors/rtmode_*.py` with `rt`, as the driver does, since every
executable holds `runtime.py`'s code. `make irsame REF=<commit>` (default
`HEAD`) builds that commit's compiler in `build/ref/`, cached by commit, and compares it with
`./pystachy`; `make irsame-py` compares the CPython-hosted compilers. `make check-ir` compiles
every program of the corpus, and `runtime.py`, with `PYSTACHY_IRCHECK=1` and runs `llvm-as` on
its IR; a program
that does not compile fails it, as an internal error and a rejected IR do, and so do effect
summaries of a `tests/ir/NAME.py` other than the ones its `NAME.fx` lists (`PYSTACHY_IRFX=1`
prints them), and runtime calls other than its `NAME.calls` lists (for each function, the
`pys_` functions it calls). `tests/ir/*.py` probe code-generation paths the other programs
never take (dead code after `return`, templates instantiated during a look-ahead, nested
templates, guards repeated in one function): these two tools compile them, but they never
run; `tests/ir/pending/` holds the probes of open compiler bugs. Both
need only POSIX sh, run in `PYSTACHY_JOBS` workers, and take a few seconds.

## Syntax errors against CPython

`tools/syntax_sweep.py` compares the syntax errors `pystachy check` reports with CPython's
`compile()`: over CPython 3.13's standard library and the installed packages (5,701 files)
the two agree everywhere except 19 valid files Pystachy cannot parse (tabs in indentation,
`\N{...}` escapes, an f-string field that reuses its quote).

## Continuous integration

`.github/workflows/ci.yml`
runs `make verify` on every push and pull request (ubuntu-24.04, LLVM 18 from apt,
Python 3.13), within a 45-minute time limit, and uploads the report as an artifact.
