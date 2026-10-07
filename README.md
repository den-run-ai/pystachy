# Pystachy — a self-hosting compiler for a static subset of Python

Pystachy compiles a statically typed subset of Python to native code through LLVM. It is
built on the design of Ouro v1 (*ouroboros*, the snake that eats its own tail). The
compiler is a single file, `pystachy.py`, written in that same subset: CPython can run
it, and it can compile itself. The native compiler it produces reproduces its own
23k-line LLVM IR byte for byte.

```
$ make                                  # bootstrap: CPython -> stage1 -> stage2 -> stage3
fixed point: stage1 == stage2 == stage3 (23462 lines of IR)
$ ./pystachy run bench/nbody.py         # JIT: LLVM ORC via lli
$ ./pystachy build bench/nbody.py -o nbody  # AOT: native executable
$ ./pystachy ir prog.py                 # print the LLVM IR
$ make test                             # differential tests against CPython
```

Requirements: LLVM/clang 18 (`clang`, `llvm-link`, `opt`, `lli`, `llvm-as`) and, for the
first bootstrap step only, CPython 3 (tested with 3.13). Set
`PYSTACHY_LLVM=/usr/lib/llvm-18/bin` if the tools are not on `PATH` under those names.

| file | lines | contents |
|---|---:|---|
| `pystachy.py` | 2,419 | lexer 189 · parser 495 · types and tables 173 · type checker + IR generator 1,464 · driver 80 |
| `runtime.c` | 593 | strings, lists, dicts, formatting, I/O — linked into every program as LLVM bitcode |
| `tests/` | 16 programs + 20 rejection cases | each program must print exactly what CPython prints |

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
print(f"total {total(cart):.2f}", cart[0], stock)
# total 18.25 Item(name='pen', price=1.5, qty=4) {'pen': 4, 'book': 1}
```

## The language

Pystachy is Python with types made static and the dynamic machinery removed. Pystachy programs
are ordinary Python 3 files: they run unchanged under CPython and, apart from the
deviations listed below, print exactly what CPython prints. Constructs Pystachy cannot run
faithfully are rejected at compile time with a `file:line: error:` message rather than
miscompiled.

**Types.** `int` (64-bit), `float` (IEEE double), `bool`, `str`, `list[T]`, `dict[K, V]`
(keys `int` or `str`), `tuple[A, B, ...]` (up to 9 elements), user classes,
`Optional[C]` / `C | None` for class types, and `None` as a return type. `typing`
spellings (`List`, `Dict`, `Optional`) and string forward references work.

**Typing rules.**
- Function parameters are annotated; a missing return annotation means `-> None`.
- Each variable has one type for its lifetime, fixed by its annotation or first assignment.
- Empty `[]` and `{}` take their type from context: an annotation, a parameter, a field,
  or the variable being assigned.
- No silent `int` → `float` conversion when assigning or passing arguments: CPython would
  keep an `int`, so `x: float = 1` is rejected (write `1.0`). Arithmetic mixes freely.
- Python scoping: a name assigned in a function is local to it; `global` opts out.
- Class fields come from class-body annotations or from `self.x = ...` in `__init__`,
  typed by annotation, parameter, literal, constructor or function call.

**Statements.** assignment (chained, tuple unpacking, swaps), annotated and augmented
assignment, `if`/`elif`/`else`, `while`, `for` over `range`, lists, strings, dicts,
`.items()`/`.keys()`/`.values()`, `enumerate`, `zip` and `reversed`, `break`, `continue`,
`return`, `pass`, `global`, `del`, `assert`, `raise` (aborts the program), `def`, `class`,
`@dataclass`, docstrings, and `import`/`from` (accepted; `sys`, `os`, `math` are built in).

**Expressions.** literals (decimal, hex and `_`-separated ints, floats, strings with all
common escapes, triple quotes), f-strings with `!r` and format specs (`{x:>8.3f}`,
`{n:,}`, `{v:08x}`, ...), arithmetic with Python semantics (`//` and `%` floor,
`/` is true division), bitwise ops, chained comparisons, `in`/`not in` (str, list,
dict, tuple), `is`/`is not`, `and`/`or` returning operands, `not`, conditional
expressions, keyword and default arguments, indexing with negative indices, slicing,
list/dict/tuple displays, list comprehensions and generator arguments
(`sum(x * x for x in xs)`), and operator overloading (`__add__`, `__eq__`, `__lt__`,
`__len__`, `__str__`, `__repr__`, ...) resolved statically.

**Library.** `print`, `len`, `str`, `repr`, `int`, `float`, `bool`, `ord`, `chr`, `abs`,
`min`, `max`, `sum`, `sorted`, `list`, `dict`, `round`, `any`, `all`, `input`, `open`;
the common `str`, `list`, `dict` and file methods; `sys.argv/exit/stdout/stderr`,
`os.system/getpid/getenv/path.exists`, and `math` functions and constants.

**Removed on purpose** — each would require a dynamic runtime or a large compiler
feature: exception handling (`try`, `with`), generators, lambdas and closures,
inheritance, `*args`/`**kwargs`, sets, dict and multi-clause comprehensions, slice steps, first-class
functions, `isinstance`/`getattr`/`eval`, user modules, `bytes`, and arbitrary-precision
integers.

**Deviations from CPython** (the program compiles but can behave differently):
- `int` is 64-bit two's complement and wraps on overflow.
- `str` is a byte string: `len` and indexing count UTF-8 bytes. ASCII behaves exactly
  like CPython and non-ASCII text passes through unchanged.
- Memory is never freed (bump allocation), which suits batch programs like compilers.
- `dict.keys()`, `.values()` and `.items()` return list snapshots.
- A runtime error prints only the last line of CPython's traceback (for example
  `IndexError: list index out of range`) and exits with status 1 after flushing stdout.
  Deep recursion overflows the stack instead of raising `RecursionError`, and
  `int ** negative` is an error instead of a float.

## How it works

```
 source ──► Lexer ──► Parser ──► AST ──► Gen: type check + emit LLVM IR (one pass)
                                                     │  text, no LLVM bindings
                       runtime.c ──clang──► runtime.bc
                                                     ▼
                                 llvm-link --only-needed (program + runtime)
                             ┌───────────────────────┴───────────────────────┐
     pystachy run  (JIT tier)    ▼                         pystachy build (AOT tier)  ▼
     opt mem2reg,instcombine,simplifycfg               clang -O2 on the whole module
     lli: ORC JIT for the host CPU                     native executable
```

- **One pass from AST to IR.** After a declaration pass collects classes, fields and
  function signatures, `Gen` walks each function once, inferring expression types
  bottom-up while emitting IR. An expected type (`want`) flows top-down to type empty
  literals and `None`. Types are canonical strings (`dict[str,list[int]]`), so the
  compiler needs no type objects.
- **SSA by delegation.** Locals live in `alloca` slots; LLVM's `mem2reg` turns them into
  SSA registers. Short-circuit operators, conditional expressions and comparison
  chains use `phi` nodes directly.
- **One value model.** Scalars map to `i64`, `double` and `i1`; strings, containers,
  tuples and objects are pointers. Container elements are uniform 8-byte slots, so one
  C implementation of `list`/`dict`/`tuple` serves every element type with no
  per-type code generation.
- **Type descriptors.** Generic operations (`repr`, `==`, ordering, `sort`, `in`) receive
  a tiny string describing the static type — `LDsi` is `list[dict[str,int]]` — and the
  runtime interprets it recursively.
- **Python semantics in the runtime.** Floor division and modulo, float `repr` (shortest
  round-trip digits), `str.split`, insertion-ordered dicts, stable merge sort, string
  `repr` quoting rules, and Python's format-spec mini-language are all implemented to
  match CPython's output.
- **Whole-program optimization.** The runtime is linked into each program as bitcode and
  optimized together with it, so `xs[i]` inlines to a bounds check and a load, and loops
  over lists vectorize. clang tags the runtime with `target-cpu`/`target-features`,
  which makes LLVM refuse to inline it into attribute-less generated code; the driver
  strips those attributes when building `runtime.bc`.
- **Two tiers.** `run` favors latency: a three-pass pipeline (SSA construction, peephole,
  CFG cleanup) followed by ORC JIT compilation for the host CPU. On the largest program
  (the compiler itself) this is about 4× faster to start than `-O2`. `build` favors
  throughput: the full `-O2` pipeline over program and runtime together.
- **Bootstrap.** The compiler is written in the subset, so CPython executes it
  directly (stage 0). `make` then checks the fixed point: the stage-1 binary (built by
  CPython-hosted Pystachy) and the stage-2 binary (built by stage 1) must emit IR identical
  to CPython-hosted Pystachy's, byte for byte. That identity is a strong end-to-end test:
  any semantic divergence between Pystachy and CPython inside the compiler shows up as a
  diff.

## Milestones

| | milestone | result |
|---|---|---|
| M0 | design | subset defined; LLVM 18 toolchain chosen: emit textual IR, let LLVM do SSA, optimization, JIT and codegen |
| M1 | runtime and pipelines | `runtime.c`; JIT (`opt`+`lli`) and AOT (`clang`) verified on hand-written IR |
| M2 | front end | indentation-aware lexer with f-strings; recursive-descent parser over one uniform `Node` type; validated on the compiler's own source |
| M3 | types and codegen | one-pass type checker and IR generator; first programs ran end to end |
| M4 | self-hosting | fixed point reached after fixing one real bug: the hidden index of a `for` loop was not reset, so nested loops ran once |
| M5 | hardening | differential tests vs CPython, rejection tests, whole-program inlining, JIT tiering, benchmarks |

Bugs the process caught: the nested-loop index (found by the bootstrap, as methods
landing on the wrong class); `print(d, d.setdefault(...))` must evaluate every argument
before printing any; `x in "int float bool"` in the compiler was a substring test, not set
membership; an expected type leaked from a global into a same-named local; hex
literals beyond 64 bits saturated silently in the native compiler but not under CPython.

## Testing

`tests/run.sh` runs every `tests/*.py` twice — JIT and AOT — and compares stdout plus
exit status with the output CPython recorded in `tests/*.out`, feeding `tests/*.in` as
stdin where present. Programs cover arithmetic edge cases, strings and formatting,
lists, dicts, tuples, classes, dataclasses, `Optional` linked structures, operator
overloading, control flow, file and process I/O, runtime errors, classic algorithms, and
a small interpreter. Each `tests/errors/*.py` must be rejected with the message on its
first line. Current result: **52 passed, 0 failed** with both the CPython-hosted and the
self-compiled compiler.

## Performance

`bench/run.sh` on a 2-core x86-64 VM (CPython 3.13, LLVM 18). JIT times include
compilation; outputs are checked against CPython's.

| benchmark | CPython | Pystachy JIT | Pystachy AOT | AOT speedup |
|---|---:|---:|---:|---:|
| fib(35) — calls | 1.72 s | 0.15 s | 0.03 s | 53× |
| mandelbrot — float loops | 2.81 s | 0.23 s | 0.11 s | 27× |
| n-body — floats, objects | 3.94 s | 0.47 s | 0.10 s | 38× |
| spectral norm — nested loops | 2.81 s | 0.40 s | 0.03 s | 109× |
| sieve — 4M-element list | 2.61 s | 0.72 s | 0.42 s | 6× |
| word count — strings, dicts | 0.42 s | 0.39 s | 0.15 s | 3× |

The sieve runs at the speed of the equivalent C program over 8-byte elements (0.43 s):
it is memory-bound. String- and dict-heavy code spends its time in the C runtime, as
CPython does, so the gain is smaller. The native compiler compiles itself in 0.03 s,
against 0.24 s when CPython runs it; run under the JIT, it compiles itself in 1.7 s
including JIT compilation, again producing identical IR.

## Natural next steps

Garbage collection (Boehm GC drops into `pys_alloc` for AOT builds), exception
handling via LLVM `invoke`/landing pads, single inheritance with vtables, and
`set`/`frozenset` on top of the existing dict table.
