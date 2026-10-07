# Pystachy — a self-hosting compiler for a static subset of Python

Pystachy compiles a statically typed subset of Python to native code through LLVM. The
compiler is a single file, `pystachy.py`, written in that same subset: CPython can run it,
and it can compile itself. The native compiler it produces reproduces its own 44k-line
LLVM IR byte for byte. Programs are ordinary Python files that print exactly what CPython
prints, apart from a short list of documented deviations; anything Pystachy cannot run
faithfully is rejected at compile time with a `file:line: error:` instead of miscompiled.

```
$ make                                  # bootstrap: CPython -> stage1 -> stage2 -> stage3
fixed point: stage1 == stage2 == stage3 (43805 lines of IR)
$ ./pystachy run bench/nbody.py         # JIT: LLVM ORC via lli
$ ./pystachy build bench/nbody.py -o nbody  # AOT: native executable
$ ./pystachy ir prog.py                 # print the LLVM IR
$ make test                             # differential tests against CPython
$ make verify                           # everything below, with a JSON report
```

Requirements: LLVM/clang 18 (`clang`, `llvm-link`, `opt`, `lli`, `llvm-as`) and, for the
first bootstrap step only, CPython 3 (tested with 3.13). Set
`PYSTACHY_LLVM=/usr/lib/llvm-18/bin` if the tools are not on `PATH` under those names.

| file | lines | contents |
|---|---:|---|
| `pystachy.py` | 3,706 | lexer 263 · parser 590 · types, tables and the definite-assignment pass 262 · type checker + IR generator 2,467 · driver 105 |
| `runtime.c` | 1,228 | garbage collector, strings, lists, dicts, generic repr/compare, formatting, I/O |
| `tests/` | 90 programs, 51 rejection cases, 3 deviation cases | each program must print exactly what CPython prints, JIT and AOT |

A taste — this is ordinary Python, and Pystachy and CPython print the same line:

```python
from dataclasses import dataclass


@dataclass
class Item:
    name: str
    price: float
    qty: int = 1


def total(items: list[Item]) -> float:
    return sum([it.price * it.qty for it in items])


cart = [Item("pen", 1.5, 4), Item("book", 12.25)]
stock: dict[str, int] = {}
for it in cart:
    stock[it.name] = stock.get(it.name, 0) + it.qty
print(f"total {total(cart):.2f}", cart, stock, Item("pen", 1.5, 4) in cart)
# total 18.25 [Item(name='pen', price=1.5, qty=4), Item(name='book', price=12.25, qty=1)] {'pen': 4, 'book': 1} True
```

## Where it comes from

Pystachy is built on the design of **Ouro v1** (*ouroboros*), one of four self-hosting
Python-subset compilers that were compared before this repository was started: Ouro v1
(LLVM), Ouro v2 (WebAssembly GC) and two MiniPy compilers (C). Ouro v1 had the broadest
subset, matched CPython's output most closely, compiled in linear time, ran fastest and was
the cheapest to extend (a builtin is one table line plus one C function). The reviews also
named its weaknesses, and Pystachy addresses them:

| review finding about Ouro v1 | Pystachy |
|---|---|
| memory is never freed | a conservative mark-and-sweep collector in `runtime.c`, no dependencies |
| ints wrap silently on overflow | checked arithmetic: `OverflowError` (MiniPy's choice) |
| a variable set on one branch reads as 0 | a definite-assignment pass; reads that may fail raise `UnboundLocalError`/`NameError` |
| mutable default arguments are recreated per call | defaults are evaluated once, when `def` runs |
| a zero `range` step loops silently | `ValueError` |
| attribute access through `None` is undefined behaviour | `AttributeError`, CPython's `None` rules for `==`, `str()` |
| unknown imports are silently ignored | imports are checked; aliases and `from` imports work |
| driver writes fixed `/tmp` files via `os.system` | a private `mkdtemp` directory, removed on every path |
| type checking and emission are one class with no IR | still true: a typed IR is the main next step (below) |

Ouro v2 contributed tests (`tests/ouro2_*.py`) and the idea of a second backend; MiniPy
contributed checked arithmetic, strict definite assignment and its verification
discipline: sanitizer builds, a Python-free native stage and a machine-readable report.
Two rounds of adversarial differential testing against CPython followed; every divergence
they found is now fixed, rejected at compile time, or listed under *Deviations*.

## The language

Pystachy is Python with types made static and the dynamic machinery removed.

**Types.** `int` (64-bit), `float` (IEEE double), `bool`, `str`, `list[T]`, `dict[K, V]`
(keys `int` or `str`), `tuple[A, B, ...]` (up to 9 elements), user classes,
`Optional[C]` / `C | None` for class types, and `None` as a return type. The `typing`
spellings (`List`, `Dict`, `Tuple`, `Optional`, `TextIO`) work when imported from `typing`,
and string forward references work.

**Typing rules.**
- Function parameters are annotated; a missing return annotation means `-> None`.
- Each variable has one type for its lifetime, fixed by its annotation or first assignment.
- Empty `[]` and `{}` take their type from context: an annotation, a parameter, a field,
  or the variable being assigned. `None` in a display takes the type of its neighbours.
- No silent `int` → `float` conversion when assigning or passing arguments: CPython would
  keep an `int`, so `x: float = 1` is rejected (write `1.0`). Arithmetic mixes freely.
- Python scoping: a name assigned in a function is local to it; `global` opts out.
- Class fields come from class-body annotations or from `self.x = ...` in `__init__`,
  typed by annotation, parameter, literal, constructor, method or function call.

**Statements.** assignment (chained, tuple and list unpacking, swaps), annotated and
augmented assignment (`+=` on lists extends in place; `__iadd__` & co are honoured),
`if`/`elif`/`else`, `while`, `for` over `range`, lists, strings, dicts,
`.items()`/`.keys()`/`.values()`, `enumerate` (with `start`), `zip` and `reversed`,
`break`, `continue`, `return`, `pass`, `global`, `del`, `assert`, `raise` (aborts the
program), `def`, `class`, `@dataclass`, docstrings, and `import`/`from` of `sys`, `os`,
`os.path`, `math`, `tempfile`, `typing`, `dataclasses` and `__future__`.

**Expressions.** literals (decimal, hex, octal, binary and `_`-separated numbers; strings
with every escape except `\N{...}`, raw and triple-quoted strings, implicit
concatenation), f-strings with `!r`, `!s`, `!a`, `=`, nested format specs and CPython's
complete format-spec mini-language, arithmetic with Python semantics (`//` and `%` floor,
`/` is correctly rounded true division, exact int/float comparison), bitwise ops,
chained comparisons, `in`/`not in`, `is`/`is not`, `and`/`or` returning operands,
`not`, conditional expressions, keyword and default arguments, negative indices,
slicing, list/dict/tuple displays, list comprehensions and generator arguments
(`any(...)`/`all(...)` stop early), and operator overloading resolved statically:
`__add__` & co, the in-place forms, `__eq__`, rich comparisons with CPython's reflection
rules (`a < b` tries `b.__gt__(a)`), `__len__`, `__bool__`, `__str__`, `__repr__` and
`__format__`. Objects inside lists, dicts and tuples compare, sort and print through
their own methods.

**Library.** `print`, `len`, `str`, `repr`, `ascii`, `int`, `float`, `bool`, `ord`, `chr`,
`abs`, `min`, `max`, `sum`, `sorted`, `list`, `dict`, `round`, `divmod`, `pow` (also
modular), `any`, `all`, `input`, `open`; the common `str`, `list`, `dict` and file
methods; `sys.argv/exit/stdout/stderr/maxsize`, `os.system/getpid/getenv/remove/rmdir/
path.exists`, `tempfile.mkdtemp`, and the `math` functions and constants, which raise
CPython's domain and range errors.

**Removed on purpose** — each would require a dynamic runtime or a large compiler
feature: exception handling (`try`, `with`), generators, lambdas and closures,
inheritance, `*args`/`**kwargs`, sets, dict and multi-clause comprehensions, slice steps,
first-class functions, `isinstance`/`getattr`/`eval`, user modules, `bytes`, complex
numbers and arbitrary-precision integers.

**Deviations from CPython** (the program compiles but can behave differently):
- `int` is 64-bit. Where CPython would produce a bigger int, including an intermediate
  result or `int()` of a long string, Pystachy raises `OverflowError` instead of
  wrapping. `int ** negative int` is a `ValueError` (the result type would be dynamic),
  and so is a negative float to a fractional power (CPython returns a complex).
- `str` is a byte string holding UTF-8: `len` and indexing count bytes, and `chr(i)` for
  `i < 256` is that byte. ASCII behaves exactly like CPython; escapes such as `\xe9` and
  `€` produce UTF-8, and format widths count code points.
- `dict.keys()`, `.values()` and `.items()` return list snapshots.
- A runtime error prints only the last line of CPython's traceback (without `NameError`'s
  "Did you mean" hints) and exits with status 1 after flushing stdout. Deep recursion
  overflows the stack instead of raising `RecursionError`.
- Floats are unboxed, so a NaN has no identity: `nan in [nan]` is `False`, and the order
  `sort` gives lists containing NaN can differ. `sort` is a stable merge sort, so the
  sequence of `__lt__` calls differs from timsort's (the result does not). The sum of an
  empty `list[float]` is `0.0`, where CPython returns the int `0`.
- An import binds its names for the whole program, wherever it appears.
- Memory is reclaimed by a conservative collector, not reference counting: garbage is
  freed in batches and there are no finalizers.

**Rejected rather than miscompiled** (CPython would run these): a function, class,
method or import name bound twice, or a name that is both a variable and a function,
class or import; a class-body default that names an earlier class attribute (Pystachy
has no class scope); a local read textually before its first assignment (declare it
first: `x: int`); a module-level read of a global that only functions assign (declare it
at module level); comparison dunders that do not return `bool`, `__str__`/`__repr__`
that do not return `str`, methods without `self`; f-strings that reuse their own quote
inside a field (PEP 701) and `\N{...}` escapes.

## How it works

```
 source ──► Lexer ──► Parser ──► AST ──► Flow: definite assignment (marks reads to check)
                                            │
                                            ▼
                               Gen: type check + emit LLVM IR (one pass), text only
                                            │
            runtime.c ──clang──► runtime.bc │ runtime.o
                        ┌───────────────────┴──────────────────────┐
  pystachy build (AOT)  ▼                                          ▼  pystachy run (JIT)
  llvm-link program + runtime.bc                 opt mem2reg,instcombine,simplifycfg
  clang -O2 on the whole module                  lli: ORC JIT of the program, linked
  native executable                              with the precompiled runtime.o
```

- **One pass from AST to IR.** After a declaration pass collects classes, fields and
  function signatures, `Gen` walks each function once, inferring expression types
  bottom-up while emitting IR. An expected type (`want`) flows top-down to type empty
  literals and `None`. Types are canonical strings (`dict[str,list[int]]`), so the
  compiler needs no type objects.
- **Definite assignment.** Before code generation, `Flow` walks every scope with the set
  of variables assigned on every path (merging `if` branches, leaving `while True` only
  through its breaks). Reads it cannot prove are marked, and only those test an "is
  assigned" flag that LLVM removes again where it can; fields that `__init__` may leave
  unassigned get a hidden flag in the object. Globals read in functions are safe when
  module code assigned them before its first call into user code, and calls to a
  function before its `def` has run raise `NameError`. The compiler itself needs none of
  these checks.
- **Checked arithmetic, cheap errors.** `+`, `-` and `*` use LLVM's `*.with.overflow`
  intrinsics; every failure (overflow, `None` receiver, unassigned variable) branches to
  one cold block per function and message. `self` is marked `nonnull`, so the `None`
  checks vanish inside methods.
- **SSA by delegation.** Locals live in `alloca` slots; LLVM's `mem2reg` turns them into
  SSA registers. Short-circuit operators, conditional expressions and comparison chains
  use `phi` nodes directly.
- **One value model.** Scalars map to `i64`, `double` and `i1`; strings, containers,
  tuples and objects are pointers. Container elements are uniform 8-byte slots, so one C
  implementation of `list`/`dict`/`tuple` serves every element type.
- **Type descriptors.** Generic operations (`repr`, `==`, ordering, `sort`, `in`) receive a
  tiny string describing the static type — `LDsi` is `list[dict[str,int]]` — and the
  runtime interprets it recursively, comparing sequences the way CPython does (first
  unequal pair, identity first). Objects appear as `O<id>`: the runtime calls back into
  `pys_obj_eq/cmp/repr`, a switch the compiler emits over the classes that occur in
  containers, with small per-class helpers built from each class's `__eq__`, rich
  comparisons and `__repr__`. Dataclass `__repr__` (cycle-safe) and `__eq__` are written
  by the compiler and generated only if used.
- **Memory.** `runtime.c` includes a conservative, non-moving mark-and-sweep collector
  that needs nothing beyond the C library. Small objects come from 64 KiB chunks in 40
  size classes, carved from 1 MiB arenas; larger objects get blocks of their own. A
  two-level page map finds the object behind any word, interior pointers included, in
  O(1). Strings, buffers and dict index arrays are allocated pointer-free and never
  scanned. The roots are the C stack and callee-saved registers, the runtime's statics,
  and the program's pointer-typed globals: the generated `@main` passes `pys_init` its
  frame address and a table of those globals, because under the JIT they live in memory
  no scanner would find. A collection runs once max(32 MiB, live bytes) have been
  allocated since the last one, so the heap stays near twice the live set.
  `PYSTACHY_GC_STRESS=N` collects every N allocations; `PYSTACHY_GC=off` and
  `PYSTACHY_GC=stats` turn collection off or print a summary at exit.
- **Python semantics in the runtime.** Floor division and modulo, float `repr` (shortest
  round-trip digits), `round` with exact half-even rounding, Neumaier-compensated `sum`,
  `int()`/`float()` string grammar, `str.split`, insertion-ordered dicts, stable merge
  sort, string `repr` quoting, and the format-spec mini-language are implemented to
  match CPython's output, error messages included.
- **Whole-program optimization.** For `build`, the runtime is linked into each program as
  bitcode and optimized together with it, so `xs[i]` inlines to a bounds check and a
  load. clang tags the runtime with `target-cpu`/`target-features`, which makes LLVM
  refuse to inline it into attribute-less generated code; the driver strips those
  attributes when building `runtime.bc`.
- **Two tiers.** `run` favors latency: a three-pass pipeline over the program alone, then
  ORC JIT compilation linked against a cached, precompiled `runtime.o`. `build` favors
  throughput: the full `-O2` pipeline over program and runtime together. The driver
  works in a private `tempfile.mkdtemp()` directory; `PYSTACHY_CFLAGS` adds clang flags
  (such as sanitizers) to the runtime and the AOT link, with a runtime cache per flag set.
- **Bootstrap.** The compiler is written in the subset, so CPython executes it directly
  (stage 0). `make` then checks the fixed point: the stage-1 binary (built by
  CPython-hosted Pystachy) and the stage-2 binary (built by stage 1) must emit IR
  identical to CPython-hosted Pystachy's, byte for byte. Any semantic divergence between
  Pystachy and CPython inside the compiler shows up as a diff.

## Testing and verification

`tests/run.sh` runs every `tests/*.py` twice — JIT and AOT — and compares stdout plus exit
status with what CPython recorded in `tests/*.out` (stdin from `tests/*.in`), and the last
stderr line with `tests/*.err` where CPython reported an error. Each `tests/errors/*.py`
must be rejected with the message on its first line, and each `tests/deviations/*.py` must
print its hand-written expected output. The programs cover arithmetic and overflow edges,
strings, escapes and f-strings, a 400-case sample of the format-spec language, lists,
dicts, tuples, classes, dataclasses, `Optional` structures, rich comparisons, defaults,
imports, definite assignment, runtime errors, garbage-collector churn, classic
algorithms, a small interpreter, and 16 programs from Ouro v2. Current result:
**237 passed, 0 failed** with both the CPython-hosted and the self-compiled compiler.

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
- **benchmarks** — output equal to CPython's, with timings.

The garbage collector is additionally checked under stress: the whole test suite passes
with `PYSTACHY_GC_STRESS=1` (a collection at every allocation), and the native compiler
reproduces its own IR while collecting every few allocations. `.github/workflows/ci.yml`
runs `make verify` on every push and pull request (ubuntu-24.04, LLVM 18 from apt,
Python 3.13) and uploads the report as an artifact.

## Performance

`bench/run.sh` on a 4-core x86-64 VM (CPython 3.13, LLVM 18). JIT times include
compilation; outputs are checked against CPython's.

| benchmark | CPython | Pystachy JIT | Pystachy AOT | AOT speedup |
|---|---:|---:|---:|---:|
| fib(35) — calls | 1.19 s | 0.11 s | 0.05 s | 22× |
| mandelbrot — float loops | 1.78 s | 0.12 s | 0.06 s | 31× |
| n-body — floats, objects | 2.49 s | 0.16 s | 0.04 s | 57× |
| spectral norm — nested loops | 1.50 s | 0.20 s | 0.02 s | 71× |
| sieve — 4M-element list | 1.01 s | 0.27 s | 0.21 s | 5× |
| word count — strings, dicts | 0.25 s | 0.14 s | 0.08 s | 3× |

The sieve is memory-bound, and string- and dict-heavy code spends its time in the C
runtime, as CPython does, so their gains are smaller. Integer arithmetic is
overflow-checked, which costs most on call-heavy integer code: `fib` takes 0.052 s instead
of the 0.027 s of Ouro v1's wrapping arithmetic, because LLVM can no longer turn
`fib(n - 1) + fib(n - 2)` into a loop; the other benchmarks are unaffected. The JIT tier
starts a program in about 50 ms. The collector keeps peak memory near the live set: ten
million short-lived strings peak at 35 MiB instead of 376 MiB with Ouro v1's bump
allocator, and building and discarding fifty 2M-element lists at 50 MiB instead of
1.5 GiB, while running faster (0.63 s instead of 0.84 s, and 0.37 s instead of 2.25 s).
The native compiler compiles itself in 0.07 s, against 0.35 s when CPython runs it.

## Next steps

- **A typed intermediate representation.** Type checking and IR emission still happen in
  one pass over the AST. A small typed IR between them would allow language-level
  optimizations (redundant dict lookups, bounds-check hoisting) and further backends.
- **A WebAssembly GC backend**, Ouro v2's design: the engine supplies memory management
  and tiered compilation, and the runtime can be written in the subset itself.
- Exception handling via LLVM `invoke`/landing pads, single inheritance with vtables, and
  `set`/`frozenset` on top of the existing dict table.
