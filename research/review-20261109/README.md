# Pystachy review, 9 November 2026

Independent check of main `c1796654` for bugs, gaps, performance, architecture and CPython
porting. Research material: not for merging (`research/` stays off production branches).

- Compiler under test: `make` at `c1796654` (LLVM 18.1.3, x86-64 Linux, 4 cores, 15 GiB).
- Reference: CPython 3.13.18 (the container's; the repository pins 3.13.16).
- Timings are single runs on a shared VM. Treat ratios under about 1.3x as noise.
- Prepared with Claude Code assistance.

## Summary

| Area | Result |
|---|---|
| Correctness | About 1,500 hand-written checks and 519 random programs show no output difference from CPython beyond documented deviations. One new compiler bug: valid arithmetic is rejected in union-typed contexts (20 of those programs). A fix is validated locally. |
| Performance | Most workloads run 2x to 130x faster than CPython. Five paths run at or below CPython speed, each with a profiled cause. A 35-line runtime prototype makes the compiler's own parser 23% to 25% faster. |
| Start-up | A one-line program that imports `re`, `argparse` or `textwrap` takes 1.4 s to JIT. For tiny programs the program cache costs more than it saves. |
| Architecture | Inherited methods compile once per subclass. A 100-level `super()` chain cannot compile. Retries re-parse every module. |
| Porting | `os.path.basename`, `dirname`, `splitext` and eight more are rejected although the shipped `posixpath` implements them. |

## 1. Bugs

### 1.1 Arithmetic on a conditional or boolean expression is rejected in union contexts (new)

```python
def f(a: int, c: int) -> int | str:
    return (a if a > 0 else c) * 2      # CPython: 6

print(f(3, 4))
# error: closed union arithmetic requires narrowing with isinstance() first
```

The left operand may be a conditional expression, or an `or`/`and` that holds one. The
rejection occurs wherever the result is wanted as a closed union: a return, an annotated
variable or field, a `dict[str, int | str]` value, a call argument, a list or tuple item.
With `int | float` the code compiles but runs boxed union arithmetic, and `**`, `&`, `|`, `^`,
`<<` and `>>` are rejected. Swapping the operands or naming the operand avoids it.

Cause: `gen_expr` compiles a binary operator's left operand with the whole expression's
expected type (`expressions.py`, the `binop` case; `gen_wexpr` does the same for masked `&`).
`gen_ifexp` then boxes both arms as that union, and `arith` receives a union operand.

How it was found: the random-program generator `fuzz/gen.py` hit it in 20 of 519 programs.
A second generator, `fuzz/gen2.py`, stores well-typed expressions into union-typed targets:
main rejects 262 of its first 400 programs.

Candidate fix: `prototype/union-ifexp-operand-fix.patch`. A helper, `left_operand`, compiles
such operands so that arms of one scalar type keep that type. Arms of two types make the union
as before, with the first arm boxed at its edge. It touches `expressions.py` and two `Gen`
forwarders.

Evidence for the fix is in the [validation log](#validation-log). Before merging: record
`.out` with the pinned 3.13.16 (this one used 3.13.18) and run the full matrix.

Not covered by the fix: arms of a promoting-int type (`# pystachy: python-int`) still take
the old path.

### 1.2 Latent limit found by reading (not reproduced)

A dict's index stores entry numbers as `int32_t` with no guard (`runtime.c`, `dadd` and
`build`). Past 2**31 - 1 entries the number wraps negative and reads as a deleted slot. That
needs roughly 80 GiB, so it is unreachable on this machine. CPython widens its index instead.

### 1.3 Known deviation worth re-ranking: ASCII-only case mapping (#120)

`"É".lower()` returns `"É"`, and `"Ça va très".title()` returns `"ÇA Va TrèS"`. This is
documented, and `PYSTACHY_UNICODE_AUDIT=1` raises instead. It is still the one place found
where a supported program prints wrong text by default, in the project's headline use case.
The ground rule in #409 points to matching CPython or raising by default.

### 1.4 What matched

| Probe | Checks | Divergences beyond documented ones |
|---|---|---|
| `num1.py` integer edges, parsing, rounding, `math` | 157 | None |
| `num2.py` float repr, format specs, `%`, parsing | about 400 | None |
| `big1.py` promoting ints, random operands | 400 cases of about 40 operations | None |
| `re1.py` `re` patterns, flags, errors | about 190 | None |
| `order1.py` evaluation order | about 70 | None |
| `flow1.py` `try`/`finally`, loop `else`, re-raise | 24 functions | None |
| `lg1.py`, `df1.py`, `narrow1.py`, `strown.py` optimizer guards | 51 | None |
| `gen1.py`, `cls1.py`, `app1.py`, `app2.py` | 4 programs | None |
| `ovf2.py` extreme sizes, widths and indexes | about 70 | None |
| Nine probes under `PYSTACHY_GC_STRESS_PROGRAM=1` | 9 | None |
| Program-cache invalidation scenarios | 9 | None |
| `fuzz/gen.py` seeds 1 to 520, JIT; every fourth also AOT | 519 (one seed loops under CPython) | 20 rejections, all 1.1; no output difference |

## 2. Performance

`bench/mb1.py` runs 52 micro-benchmarks with checksums; all checksums match CPython.
Results are in `bench/mb1.*.txt`. Representative speedups over CPython for `build`: integer
loops 93x, method calls 30x, generators 13x, `dict[int, int]` 7x, `list.sort()` 2.4x.

The paths below are the exceptions. Costs are per operation.

| Path | CPython | Pystachy `build` | Profiled cause |
|---|---:|---:|---|
| `try: d[k]` / `except KeyError`, key missing | 118 ns | 998 ns | `_Unwind_ForcedUnwind`: 89% of about 11,700 instructions |
| `xs[i]` / `except IndexError` | 114 ns | 689 ns | Same |
| `i // 0` / `except ZeroDivisionError` | 125 ns | 711 ns | Same |
| `raise` in a callee, caught by its caller | 192 ns | 565 ns | Same |
| `next(it)` / `except StopIteration` | 169 ns | 543 ns | Same |
| `raise` and `except` in one function | 102 ns | 38 ns | Direct branch (already fast) |
| `f"{x:.3f}"` | 212 ns | 399 ns | glibc `printf_fp`: about 4,400 instructions |
| `f"{x:g}"`, `f"{x:.2e}"` | 199, 218 ns | 361, 322 ns | Same |
| `round(x, 2)` | 217 ns | 267 ns | `snprintf`, then `strtod` |
| `str(i)` | 67 ns | 56 ns | `snprintf("%lld")`: about 720 instructions |
| `repr(x)` of a float | 440 ns | 78 ns | Ryu (already fast) |
| `x in xs`, 100 ints | 439 ns | 319 ns | Generic comparator, 47 instructions per item; a hand-written loop takes 27 ns |
| `xs.index(x)`, `xs.count(x)` | 359, 673 ns | 235, 431 ns | Same |
| `s[i]`, random `i`, 2,200-character non-ASCII string | 60 ns | 739 ns | Linear scan from a hint (documented) |
| `sorted(xs, key=f)` with an int key | | | 60% of instructions in the generic comparator; `xs.sort()` uses a typed merge |

Three of these share one cause. Every `str == str` compiles to `pys_eq(a, b, "s")`, which
interprets the descriptor at run time. `pys_list_find`, `index_in`, `pys_list_count` and
keyed sorts do the same for each item. `pys_str_eq` exists but the compiler never emits it.
String literals are writable globals (their hash is cached in place), so LLVM cannot fold
the descriptor test even where it inlines.

### Prototype

`prototype/runtime-scalar-eq-fastpath.patch` adds fast paths for `str` in `pys_eq` and for
`int`, `bool` and `str` items in list search. It changes `runtime.c` only.

| Measurement | Base | Prototype | Change |
|---|---:|---:|---:|
| `pystachy check src/pystachy_compiler/expressions.py` | 79.5 ms | 60.0 ms | 25% less |
| Same, instructions (callgrind) | 734.9 M | 507.7 M | 31% less |
| `pystachy ir pystachy.py` (self-compile frontend) | 4.77 s | 4.23 s | 11% less |
| `pystachy ir` of a program importing `re` | 208 ms | 156 ms | 25% less |
| `x in xs`, 100 ints | 319 ns | 45 ns | 7.1x |
| `xs.count(x)`, 100 ints | 431 ns | 24 ns | 18x |
| `x in xs`, 100 strs | 332 ns | 107 ns | 3.1x |
| Token-kind `==` chain (`bench/streq2.py`), `build` | 0.377 s | 0.052 s | 7.2x |
| Same, `run` | 0.423 s | 0.210 s | 2.0x |

The compiler gains because `eqv` was 37.6% of the parser's instructions: `Parser.peek`
alone called it 2.06 million times for one 5,222-line file.

Checks: `make` fixed points pass, and 522 container, string, optional and promoting-int
tests pass in JIT and AOT. Not run: `make verify`, `listprobe`, `eqprobe`, GC-stress groups.
A compiler-side version (emit the length test inline, call `memcmp`) should gain more.

### Checked and not a finding

- Int-key hashing: the default mixer beats CPython's scheme on random, shifted and strided
  keys. CPython's scheme wins only for sequential keys read in order (`bench/scatdict.py`).
- Memory: peak RSS is 1.0x to 3.2x below CPython's on nine allocation workloads
  (`bench/mem.py`). A 3-million-object live set with churn runs 19x faster.
- Two loops ran 20% to 40% slower under `build` than `run`. The gap did not reproduce in
  isolation.
- A caught `KeyError` formats its message eagerly. That is 7% of its instructions, so
  deferring it would not change the picture.

## 3. Start-up and compile latency

`bench/startup/`, best of three, `PYSTACHY_PROGRAM_CACHE=0` unless stated.

| Program | CPython | Frontend | `run` | `build` | IR lines |
|---|---:|---:|---:|---:|---:|
| `print("hello")` | 11 ms | 2 ms | 32 ms | 0.36 s | 56 |
| `import re`, one `re.sub` | 17 ms | 185 ms | 1.39 s | 5.7 s | 55,848 |
| `import argparse`, one option | 22 ms | 233 ms | 1.50 s | 6.4 s | 60,694 |
| `import textwrap`, one `fill` | 17 ms | 204 ms | 1.36 s | 6.0 s | 56,557 |
| `import logging`, one record | 25 ms | 1,289 ms | 3.90 s | 13.0 s | 119,063 |
| `import json`, one `dumps` | 20 ms | 30 ms | 0.19 s | 2.1 s | 6,211 |

Where the 1.39 s for `re` goes: frontend 188 ms, `opt` 228 ms, ORC code generation 1,023 ms.
`PYSTACHY_JIT_CODEGEN=0` cuts code generation to 195 ms and the total to 0.63 s (#430).

`logging` takes three whole-program attempts (280 + 436 + 535 ms). Each attempt loads and
parses every module again: 610 of 1,250 ms. Of 500 sampled corpus programs, 26 needed more
than one attempt and one needed seven. Loading is 43% of frontend time across the sample,
and 34% (1.6 of 4.7 s) when the compiler compiles itself.

### Program cache on a tiny program

| `print("hello")` | Time | Processes | `newfstatat` calls |
|---|---:|---:|---:|
| `PYSTACHY_PROGRAM_CACHE=0` | 30 ms | | |
| Cache hit | 44 ms | 10 | |
| Cache miss | 461 ms | 74 | 173,087 |

The miss spends 260 ms in lookup before the frontend starts. #1185 covers the hit; the miss
is 15x the uncached run and is not in its scope.

## 4. Architecture

### Inherited methods compile once per receiver class

`scaling/km.py`: a base class with M methods and K subclasses that override one hook.

| K subclasses | M methods | Method bodies | IR lines | Frontend |
|---:|---:|---:|---:|---:|
| 10 | 10 | 110 | 9,634 | 28 ms |
| 40 | 10 | 410 | 35,164 | 62 ms |
| 10 | 40 | 440 | 37,234 | 61 ms |
| 40 | 40 | 1,640 | 136,564 | 246 ms |

A chain of `super().f()` calls grows quadratically: 15,572 IR lines at depth 40 and 58,152
at depth 80. At depth 100 a fully annotated program fails with "compilation needs more than
4096 template specializations".

### Other superlinear shapes (`scaling/scale.py`, `scale2.py`)

| Shape | Sizes | Frontend | Note |
|---|---|---|---|
| `==` on a base with N subclasses | 400, 800, 1,600 | 0.41 s, 1.55 s, fails | Quadratic (#625); fails on the 4,096 limit |
| N nested functions in one function | 400, 800, 1,600 | 90, 275, 1,119 ms | Quadratic time, linear IR |
| N generator functions, all called | 400, 800, 1,600 | 103, 300, 969 ms | About N**1.6 |

Sixteen other shapes grow by 1.2x to 2.9x when N doubles (2.0x is linear), including
specializations, dataclasses, methods, f-strings, long expressions and dict or list literals.
A call nested 200 deep is rejected with CPython's own "too many nested parentheses".

### Observations

- The runtime interprets type-descriptor strings for equality, search, ordering, hashing
  and `repr`. That keeps one implementation per operation but puts an interpreter in hot
  loops (section 2).
- A retry (`Rejoin`) discards the `Gen` and the `Loader`, so parsing repeats (section 3).
- `run` shells out to `opt` and compiles the whole module eagerly at `-O2`; library code
  that never runs is optimized too.
- Runtime-raised errors always unwind, even into a handler in the same function.
- An expression's expected type is passed down into operands, which is correct for empty
  containers and wrong for scalars (1.1).

## 5. CPython porting and gaps

Each line below is a compile-time rejection of a common idiom. None has its own open issue.

| Idiom | Status |
|---|---|
| `os.path.basename`, `dirname`, `splitext`, `split`, `abspath`, `normpath`, `isabs`, `expanduser`, `relpath`, `commonprefix`, `os.path.sep` | Rejected. `posixpath.basename` and the rest work: `lib/posixpath.py` is CPython's file. |
| `os.environ["X"]`, `.get()`, `in`, iteration | Rejected; only `os.getenv` works |
| `os.makedirs(p, exist_ok=True)` | Keyword rejected |
| `max(xs, default=0)`, `min(xs, default=0)` | Keyword rejected |
| `for i, (a, b) in enumerate(zip(xs, ys))` | Rejected (documented: nested iterator wrappers) |
| `Counter(x for x in xs)` | Rejected; a list works |
| `d.get(k) or "missing"` where `int | str` is expected; `x = a if c else 1.5` | Rejected: `or`, `and` and an unannotated conditional never form a scalar union |
| `int.to_bytes`, `int.from_bytes` | Missing |
| `e.args`, `e.errno`, `e.code` | Rejected (documented) |
| `__file__`, `sys.executable`, `sys.path`, `sys.stdout.isatty()` | Rejected (`__file__` documented) |
| `json.dump`, `json.load`, `indent=` | Missing (documented) |
| `os.walk`, `os.stat`, `os.chdir`, `os.cpu_count`, `time.strftime` | Missing |

`os.path` is the cheapest to close: forward the names the builtin lacks to `posixpath`.

## 6. Techniques

| Technique | Addresses | Notes |
|---|---|---|
| Typed runtime entry points for scalar cases; descriptors as the slow path | Section 2 | Prototype shows the gain. Emitting descriptors as `constant` (they need no hash cache) would let `build` fold them. |
| Lower a may-raise runtime operation with a matching local handler to a status result and a branch | `KeyError`, `IndexError`, `StopIteration`, `ValueError` | `dictfuse` and local `raise` already work this way. |
| Ryu `d2fixed` and `d2exp`, or CPython's `dtoa` modes; two-digit table for ints | Formatting | Ryu is already vendored for `repr`. |
| Per-string code-point index, built on first non-sequential access | Non-ASCII `s[i]` | PyPy's approach; keeps UTF-8 storage. |
| `optnone` on cold functions, or `-O0` first with hot loops at `-O2` | JIT latency | `-O0` halves total latency for `re` today. |
| Cache parsed modules by content hash; keep the load across retries | Frontend | Loading is 34% to 43% of frontend time. |
| Share one body among subclasses when a method does not dispatch on `self` | Section 4 | Removes the K x M growth and the depth limit. |
| Publish a program-cache entry after the run, or skip it when JIT took under 100 ms | Section 3 | |
| Random typed-program fuzzing in CI's advisory tier | 1.1 | `fuzz/gen2.py` found the bug's full extent in minutes. |

## 7. Suggested order

1. Land the fix for 1.1 after the full matrix.
2. String equality and scalar list search: runtime patch first, compiler lowering second.
3. `os.path` forwarding to `posixpath`.
4. Local-handler lowering for `KeyError` and `IndexError`.
5. Fixed-precision float formatting and `str(int)`.
6. JIT code-generation policy for library-heavy programs (#430).
7. Decide #120's default: implement, or raise on non-ASCII input.

## Validation log

Fix for 1.1 (`prototype/union-ifexp-operand-fix.patch`), built in a separate worktree at
`c1796654` plus the patch. The base compiler is `c1796654` unmodified.

| Check | Result |
|---|---|
| `make`: compiler stage 1 = 2 = 3 (882,819 IR lines); `runtime.py` IR unchanged (19,907) | Passed |
| `tools/irsame.sh` base against fixed, one shared `PYSTACHY_HOME` | 4,358 programs identical |
| `prototype/union_ifexp_operand.py`: `run`, `build`, `PYSTACHY_GC_STRESS_PROGRAM=1`, `PYSTACHY_IRCHECK=1`, `PYSTACHY_OPT=-all` | Matches CPython |
| `make test` on inference, optional, language, generics, numbers and errors/inference | 923 cases, 1,741 passed, 0 failed |
| `ruff check`; `mypy --config-file mypy.ini` | Passed; no issues in 55 files |
| `fuzz/gen2.py` seeds 1 to 400 | Base rejects 262; fixed accepts 400, all matching CPython |
| `fuzz/gen.py` seeds 1 to 520, `run`; every fourth also `build` | Base rejects 20; fixed accepts 519, all matching CPython |
| `make verify`, CI matrix, `make test-py`, macOS | Not run |

A first `irsame` run compared two checkouts and reported 264 differences. Those shown were
library paths embedded in string constants (#527). The run in the table shares one home,
which is valid here because the patch changes no library or runtime file.

Runtime prototype (`prototype/runtime-scalar-eq-fastpath.patch`), built the same way:

| Check | Result |
|---|---|
| `make` fixed points | Passed |
| `make test` on containers, strings, optional, `python_int_list*`, `python_int_dict*` | 522 passed, 0 failed |
| `make verify`, `listprobe`, `eqprobe`, GC-stress groups, `irsame` | Not run |

Main's CI on `c1796654` (push): CI, Coverage, Variants, Installation, Lint, Performance
smoke and Packages all concluded `success` by 20:27 UTC. Job-level results were not read.

## Follow-up: pull requests (10 November)

Each is one branch from main `c1796654`, validated on its own (`make` fixed points, new
regression programs in JIT and AOT, focused `make test`, `tools/irsame.sh` against main).

| Finding | Pull request | Change |
|---|---|---|
| 1.1 Arithmetic on a conditional operand in union contexts | #1199 | `left_operand()`; also covers promoting-int arms, which the prototype left out |
| Section 2: `str ==` and scalar list search | #1201 | The runtime prototype, with a zero-generic-comparison bound in `tools/eqprobe.c` |
| Section 5: `os.path` names | #1200 | Ten builtin functions in `runtime.py` and `runtime.c`, not a forward to `posixpath`: importing it costs about 50 ms a run, and it has no `abspath`, `relpath`, `expanduser` or `commonprefix` |
| Section 5: `max()`/`min()` `default=` | #1204 | With one iterable, also with `key=`; CPython's evaluation order |
| Section 5: `Counter(x for x in xs)` | #1203 | A generator argument binds `Iterable[T]` for generic classes |
| Section 5: `os.environ[...]`, `os.makedirs(exist_ok=)` | #1205 | Item reads, writes, `del`, `in`, `get()`; `os.makedirs()` |
| New: internal error typing `n or a` of an int and a promoting int | #1202 | Found while fuzzing #1199's programs as promoting-int modules |

Not addressed, with the reason:

| Finding | Why not yet |
|---|---|
| 1.2 Dict index width | No test can reach 2**31 entries here; a guard would be unverified |
| 1.3 Case mapping (#120) | A default-behavior decision (implement, or raise on non-ASCII input) |
| Caught runtime errors unwind; float formatting; `str(int)`; non-ASCII `s[i]` | Each is a runtime design change that needs its own measurements |
| JIT code generation of unused library code; program-cache miss; retries re-parse | Driver and loader policy (#430, #1185); the loader rewrites the trees it parses, so a retry cannot simply reuse them |
| Inherited methods per receiver class; 4,096-specialization limit | Compiler architecture |
| `enumerate(zip(...))`; `int.to_bytes`; `e.args`; `__file__`; `json.dump` | Not started |

## Reproducing

```sh
export PYSTACHY_REPO=/path/to/checkout PYSTACHY=/path/to/checkout/pystachy
probes/probe.sh -a probes/order1.py           # CPython against run and build
python3.13 bench/mb1.py; "$PYSTACHY" build bench/mb1.py -o mb1 && ./mb1
(cd fuzz && ./fuzz.sh 1 520 aot)              # random programs
python3.13 scaling/scale.py; python3.13 scaling/km.py
git apply prototype/union-ifexp-operand-fix.patch      # in a clean checkout, then make
git apply prototype/runtime-scalar-eq-fastpath.patch
```
