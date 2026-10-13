# Testing and verification

Pystachy's promise, that a compiled program prints what CPython prints, is checked by running
the same programs under both and comparing the results. This page describes the test suite,
the full verification run that CI performs on every push, and the tools that keep refactors
honest.

| command | what it checks |
|---|---|
| `make` | the bootstrap: the compiler built by itself reproduces its own LLVM IR byte for byte |
| `make test` | the differential tests with the native compiler, JIT and AOT (`FILES="tests/a.py tests/errors/b.py"` runs only those) |
| `make test-py` | the same tests with the compiler running on CPython |
| `make test-cache` | the cached runtime's rules, with both compilers (`tests/cache.sh`, [below](#make-verify)) |
| `make test-ffi` | the FFI's tests, JIT and AOT: C calls and the FFI's errors, and with python3's libpython, extension modules against the twins ([ffi.md](ffi.md#tests)) |
| `make bench-extended-check` | the [extended performance prototype](extended-performance.md)'s runner failure checks and small CPython/JIT/AOT checksum checks; no timing gates |
| `make verify` | the bootstrap, both test runs and the other steps under [make verify](#make-verify), with a JSON report in `build/verification.json` |
| `make irsame REF=<commit>` | a refactor changes no program's IR, message or exit status |
| `make check-ir` | every program in the corpus compiles, and the compiler's IR check and `llvm-as` accept its IR |
| `make check-runtime` | the compiler's `RUNTIME` table agrees with `runtime.c` |
| `make check-recordings` | `tests/record.sh --check`: CPython still prints every recorded expected output, every deviation still deviates, `lib/`'s copies are CPython's files, and no stray file lies in the tree ([below](#recording-expected-output)) |
| `make re-fuzz` | `lib/re`, run by CPython, against CPython's `re` on random patterns (`RE_FUZZ="N SEED"` for others) and on `test_re`'s biggest cases |
| `make dictprobe` | bounded dictionary probe counts and one string hash scan per object, including GC stress |
| `make listprobe` | empty lists release backing storage; deterministic capacity and collected live-byte checks |
| `make eqprobe` | shared container DAGs compare within a fixed comparison budget, including ordering and searches |
| `make jitprobe` | unused functions do not reach `lli`; live calls, defaults, import effects and runtime callbacks match CPython |
| `make lint` | `ruff check` (findings only, `ruff.toml`), `shellcheck` of the scripts as POSIX sh, and clang's warnings on the C sources; `pip install -r tools/requirements-dev.txt` gives the versions that CI's Lint workflow (`.github/workflows/lint.yml`) runs on every push, with `make check-recordings` after it |

## Differential tests

`tests/run.sh` runs every `tests/*.py` twice — JIT and AOT — and compares stdout plus exit
status with what CPython recorded in `tests/*.out` (stdin from `tests/*.in`), and the last
stderr line with `tests/*.err` where CPython wrote to stderr; where CPython wrote nothing
there (no `tests/NAME.err`), the program must write nothing either. An AOT build's stderr is
kept apart from its program's, and must be empty (`pystachy run` writes its own diagnostics,
before it becomes the program, to the program's stderr: they must be nothing too).
`tests/record.sh NAME` records a test's expected output from CPython, the way `tests/run.sh` runs
it ([below](#recording-expected-output)). Each `tests/errors/*.py`
must be rejected with the message on its first line (a `tests/errors/syntax_*.py` one also by
`pystachy check`): the compiler exits with status 1 and writes one line to stderr, the
diagnostic `FILE:LINE: error: MESSAGE`, which must hold that message (a crash's traceback that
happens to hold it is no rejection). Each `tests/deviations/*.py` must print its hand-written
expected output. Where `tests/NAME.path` exists, it is the module path: `PYTHONPATH` when
`tests/record.sh` records the test, `PYSTACHY_PATH` when `tests/run.sh` runs it.
`tests/run.sh COMPILER MODES FILE...` runs only the cases it names (e.g. `tests/run.sh ./pystachy jit
tests/str_*.py`). The cases run in `PYSTACHY_JOBS` workers at once (default: one per CPU), each
worker taking the next case no other has claimed, with `PYSTACHY_IRCHECK=1`: the
compiler then checks the IR it built before lowering it (every op is known, each block ends
with its one terminator, an op left as LLVM text is no call, phi or terminator, each op
defines the numbers its lowering prints, branches go to blocks of the function, a phi's
predecessors branch to it, only unwind edges reach a landing pad, and inside a `try` no call
that may raise is left without one). The optimizations that run on the IR before it is lowered
([`docs/typed-ir.md`](typed-ir.md) §7.1) can be turned off for a differential run: `PYSTACHY_OPT=-listget`
(a for loop's reads of the list it steps through, without a bounds check) or `-dictfuse` (one
hash lookup for `if k in d: d[k] += 1` and the like), and so can a choice of the lowering,
`-tupleiter` (a for loop over a tuple reads the tuple's slots, not a list of its items),
comma-separated, or `-all`; the tests pass with each one off.
The programs cover arithmetic and overflow edges,
strings (also their Unicode whitespace), escapes and f-strings, a 400-case sample of the
format-spec language, lists, dicts (also keys that collide in the hash table, and tuple keys), tuples, classes
(also their container protocol, static and class methods, and class variables), dataclasses, NamedTuples, typing's forms (`collections.abc`, `Final`, `@overload`, `TypeVar`,
`os.PathLike`), `Optional` structures, optional values (also boxed numbers) and
their narrowing (with CPython's error for each use of `None` where only a value works), rich comparisons, defaults,
imports, modules and packages (`tests/mods/`, `tests/scope/`, `tests/infer/`; imports in `try`
statements that raise or are skipped, `tests/tryimp/`, `tests/upimport/`), what the
loader decides at import time (`tests/loader/`), a program run through a symbolic link
(`tests/linked/`), CPython's syntax errors and its compiler's block, parser-stack and marshal limits, templates, empty containers typed by their first
use, loops with `else`, the `lib/` modules (`tests/lib_*.py`, and for `re` CPython 3.13.16's
`re_tests.py` and `test_re.py` cases, `tests/upstream_re_*.py`), definite assignment, sorting
(timsort's exact comparisons), loops that change what they iterate, files and the standard
streams, exceptions and exit statuses, runtime errors (also CPython's wording of the type and argument errors Pystachy reports
when it compiles), garbage-collector churn, classic
algorithms, a small interpreter, and 16 programs from Ouro v2. Where `tests/NAME.full`
exists, the program's stdout is `/dev/full`. Current result: **1931 passed, 0 failed** with
both the CPython-hosted and the self-compiled compiler.

### Recording expected output

`tests/record.sh NAME...` runs each `tests/NAME.py` under CPython as `tests/run.sh` runs it, and
writes `tests/NAME.out` (stdout, then `[exit N]`) and, where CPython wrote to stderr,
`tests/NAME.err` (the last line it wrote there); the `.out` and `.err` of a differential test are
never edited by hand. CPython runs with an environment of `PATH` alone, and `PYTHONPATH` where
`tests/NAME.path` gives one, so that nothing else of the caller's reaches a recording:
`FORCE_COLOR=1` would color CPython's tracebacks in hundreds of `.err` files, a `PYTHONPATH` add
modules to a test that has no `.path`, and `PYTHONUNBUFFERED` change what reaches a stdout the
program shares with the commands it runs. Without `LANG` and `LC_*` the locale is C, in which
CPython runs in UTF-8 mode (PEP 540), so `PYTHONUTF8=1` would change nothing: that environment
reproduces every recording. The CPython must be the one of `.python-version`, which CI uses:
another minor version is refused (3.12 prints otherwise for 28 tests), another patch version is
warned about. The one package from outside the standard library that the tests import is
`typing_extensions` (`tests/typevar_templates.py`, which Pystachy reads as `typing`), which
`pip install -r tools/requirements-dev.txt` installs.

`tests/record.sh --check` (`make check-recordings`) records every test into a temporary directory
instead of `tests/`, and fails, naming the file:

- where that differs from `tests/NAME.out` or `tests/NAME.err`: a recording edited by hand, or one
  that CPython no longer prints;
- where CPython prints what a `tests/deviations/NAME.py` must print: its stdout, the last line of
  its stderr (where Pystachy reports an uncaught exception, after flushing stdout) and its exit
  status make `tests/deviations/NAME.out`, so the deviation is gone, and the program belongs with
  the differential tests;
- where a module of `lib/` is not the CPython file whose SHA-256 [`lib/README.md`](../lib/README.md) lists;
- where a `.out`, `.err`, `.in`, `.full` or `.path` in `tests/` has no program;
- where a `*.rej`, `*.orig` or `core` file lies in the tree (`.git`, `build/` and `.claude/` aside).

It takes about 20 seconds, one test after the other; CI's Lint workflow runs it on every push.

A test program dies by no signal but SIGTERM and SIGINT: bash, as `sh`, reports a death by another
signal with the process's ID, which `tests/NAME.err` would hold. `tests/run.sh`, `tests/record.sh`
and `tests/verify.sh` set `ulimit -c 0`, so that a crash dumps no core file into the tree
(`.gitignore` lists `/core` too).

## `make verify`

`make verify` (`tests/verify.sh`) runs the whole verification and writes
`build/verification.json` with each step's result, duration and counts, the toolchain
versions, platform, git commit and a timestamp:

- **bootstrap** — stage1, stage2 and stage3 emit identical IR, for the compiler and for `runtime.py`;
- **tests-cpython / tests-native** — the differential tests with each compiler, JIT and AOT (the
  CPython-hosted one runs as `python3 -m pystachy`, whose bytecode CPython caches, checked
  against `pystachy.py`'s hash: run as a script, it would compile its 16k lines at every start);
- **tests-opt-off** — the differential tests with the native compiler and every optimization
  on the IR turned off (`PYSTACHY_OPT=-all`): the passes change no output;
- **runtime-cache** — `tests/cache.sh` (`make test-cache`) with each compiler, a private
  `PYSTACHY_HOME` and LLVM tools behind wrappers that count the runtime's builds: the cached
  runtime ([runtime-in-subset.md](runtime-in-subset.md) §1.4) is used while nothing it is built
  from changes (also by the AOT tier, and through another path to the same tools), and built
  again, its new entry replacing the old, when `runtime.py` changes by an edit of the same size
  whose mtime is set back, when `runtime.c` changes, when both change while the runtime is built
  (the run after builds the new bytes), when a tool changes and when the compiler changes;
  `PYSTACHY_CFLAGS`, `PYSTACHY_OPT` (the same passes named otherwise share one) and tools found
  through `PATH` get entries of their own; a failed `llvm-link` and a build killed after `opt`
  leave nothing a later run uses; `pystachy ext` caches its glue (`pyembed.c`, `pyext.c`) beside
  the runtime; with a tool whose times have not settled, `run` and `ext` build a runtime of their
  own and publish nothing; and the compiler run by name is found through `PATH` as the shell
  finds it (past a directory, a file that is not executable, through a symbolic link), a script
  run by CPython in the current directory without a search;
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
  take minutes); the self-compile runs on one core, so it starts when the bootstrap ends and runs
  beside the test runs;
- **benchmarks** — output equal to CPython's, with timings;
- **rtcheck** — `tools/rtcheck.py` runs `runtime.py` on CPython and compares each of its
  functions with CPython's str methods, `math` functions and `format()` (and the dict hashes
  with their formulas) on random inputs, about 290,000 cases;
- **re-fuzz** — `tools/re_fuzz.py` (`make re-fuzz`) runs `lib/re` on CPython and compares it
  with CPython's own `re`: 2,000 random patterns of all of 3.13's syntax (seed 1), some invalid on
  purpose, must compile to CPython's code or raise its error (message and position), and each
  valid one must match, split and substitute 19 random strings as CPython's `re` does, every
  other pattern on strs that hold UTF-8, as Pystachy's do; about 390,000 cases. The cases of
  `test_re.py` that `tests/upstream_re_*.py` run smaller (too many allocations for gc-stress)
  run there at upstream's size;
- **rt-abi** — `tools/rtabi.py`: every function `runtime.py` defines or declares has one LLVM
  signature in `runtime.py`, in runtime.c and in every program of the corpus (`llvm-link`
  would accept a mismatch silently);
- **ffi** — `tests/ffi/run.sh` (`make test-ffi`) with the native compiler: `@ffi.extern`'s C
  calls and the FFI's compile-time errors, and, with python3's own libpython, `pystachy ext`'s
  extension modules, against the twins in `tools/rt_cpython` ([ffi.md](ffi.md));
- **dict-probes** — `tools/dictprobe.c` counts the table slots that dict insertions and
  lookups visit for twelve key patterns that defeat a weak hash or probe sequence (`i << 46`,
  spaced ints, str keys sharing a long prefix or suffix, ...) and every shift `i << s`, with
  sequential keys as the control, at 4k to 30k keys, and fails above 3 slots per lookup: the
  counts are the same on every machine, so no timing is compared with a threshold. A test-only
  wrapper around the real string hash also counts calls and bytes: repeated, alternating,
  equal-but-distinct and tuple keys retain their caches across lookups, resize and deletion.
  `--hash-cache` runs those cache checks alone, also with collection at every allocation;
- **inherited-ast** — `tools/inheritprobe.py` counts retained and cloned AST nodes for an
  unused class method with N statements and N exception subclasses at N = 80, 160 and 320.
  Both counts must stay linear; native ir/run/build also succeed at N = 800 under 256 MiB.
  Each inherited method keeps its declaration metadata but shares an immutable body until
  it is needed, when its own class binding and definite-assignment checks are applied;
- **list-storage** — `tools/listprobe.c` retains 64 cleared lists that each held 65,536 slots,
  checks that their backing capacity is released and collected live bytes stay below 1 MiB,
  and checks empty copying, reuse and sort mutation markers, normally and with collection
  at every allocation; these are deterministic allocation checks, without RSS or timing thresholds;
- **container-eq** — `tools/eqprobe.c` compares a 32-level shared container DAG, orders it and
  searches for it in lists, normally and with collection at every allocation. More than 64
  recursive comparisons fail immediately, so an exponential traversal fails without hanging;
- **compile-limits** — `tools/compilelimits.py` checks that growing type representations,
  active signatures, branching template specializations and the signature bytes they retain
  (16 MiB per compilation) fail with bounded source diagnostics in hosted/native `ir`, JIT `run`
  and AOT `build`, under 256 MiB address space and ten CPU seconds. Finite controls check
  active-budget release and reuse of completed instances at the compilation-wide limit of 4,096
  specializations;
- **jit-dead-code** — `tools/jitprobe.py` inspects the bitcode handed to `lli` by both compilers:
  35 unused functions, including a mutually recursive pair, must be absent. Live calls, an unused
  function's default, import effects and the runtime's object comparison/representation callbacks
  must still execute as in CPython. The guard has no timing threshold;
- **scaling** — `tools/scaling.py --check` compiles generated programs of 500 and 1,000
  functions, globals, classes, modules, chained imports, `while True` breaks, `elif`s,
  comprehensions, links of a dict key's chain of values, dict lookups and global dicts with
  both compilers; the lines the CPython-hosted compiler executes, and the items its builtin
  calls copy or scan, must grow no faster than the programs.

A step that runs the differential tests passes only with as many passes as the checks the suite
holds, which `tests/verify.sh` counts from its files as `tests/run.sh` makes them (each program and
deviation once per mode, each rejection once, and `pystachy check` of the syntax tests): a run
that covered fewer cases fails, as one with a failure does. The report gives each of these steps'
`passed`, `failed` and `expected` counts. The **runtime-cache** step expects `tests/cache.sh`'s
checks the same way: 56 with the native compiler, 55 with CPython's (one `PATH` case fewer).

The steps set the `PYSTACHY_*` variables they test themselves. `tests/verify.sh` drops the
others that would change what a step checks (`PYSTACHY_OPT`, `PYSTACHY_GC`, `PYSTACHY_GC_STRESS`,
`PYSTACHY_CFLAGS`, `PYSTACHY_PATH` and the like) from its environment, and lists the ones it
found in the report's `ignored_env`; it keeps `PYSTACHY_LLVM` and `PYSTACHY_JOBS`.

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

`.github/workflows/ci.yml` runs `make verify` once per commit: on each pull request, from this
repository or a fork, with its branch merged with `main` as it is then; on each push to `main`;
and on demand for any branch. A newer push to a pull request cancels its older run; on `main`
every commit runs to the end. It runs on ubuntu-24.04 with LLVM 18, which `tools/setup.sh`
installs where the runner image lacks it, and the CPython of `.python-version`, within a
45-minute time limit, and uploads the report as an artifact. Beside it, on the same events,
`.github/workflows/lint.yml` runs `make lint` and then `make check-recordings`, with the CPython
of `.python-version` too: it needs no compiler, so a recording that CPython no longer prints is
named within a minute or two.
