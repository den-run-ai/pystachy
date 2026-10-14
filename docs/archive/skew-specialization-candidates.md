# Candidates for skewed-type specialization

**Historical report.** Measured on 14 October 2026 against `main` at `c9d1e59`, with the tools of
`fdbfe26`, on a 4-core x86-64 VM with CPython 3.13.16 and LLVM 18.1.3. Its counts and timings
describe that revision, not later compilers.

[The census](https://github.com/den-run-ai/pystachy/pull/377) ran the first step of a suggestion to
make Pystachy useful for Python without annotations: record the dynamic types at call sites, see
whether they are skewed, and specialize higher up the call stack where they are not
([selective specialization](https://dl.acm.org/doi/10.1145/223428.207119)). It found the types very
skewed. Two drafts then turned skew into specialization:
[#388](https://github.com/den-run-ai/pystachy/pull/388) (a stream union in `shlex`) and
[#389](https://github.com/den-run-ai/pystachy/pull/389) (callback identity through `bisect`). This
report asks which candidate would test the idea better, and measures three things on `main`.

## Summary

- **Polymorphism that Pystachy can express is already cheap.** A call through a base annotation
  compiles to class-tag compares and direct calls, with no indirect call. On a loop that does
  nothing but dispatch, removing dispatch entirely gains 1.22× (1.43 against 1.18 ns per call):
  an upper bound for a receiver-class specialization. #388's union showed no consistent gain.
- **No classic unannotated benchmark compiles.** Of six pyperformance 1.14.0 benchmarks, two stop on
  types (richards, float), one on a language feature (deltablue), three on modules (raytrace, chaos,
  go).
- **Recorded types fix the type errors, and find the skew.** One CPython run supplies 107 of
  Richards' annotations and clears its type errors, except where the observations do not join:
  `Task.input` holds a `Packet` 6 times, `None` 5 times and the int `10000` once (a value the idle
  task stores and never reads). DeltaBlue's `Variable.value` is an `int` in 3,754 samples and a
  `float` in 4. A static subset must reject or box these; skew says which representation to pick.
- **Richards is two edits and one compiler feature from compiling.** With the int and a stored
  `range` edited, recorded types carry it to `isinstance()` narrowing of a base-typed value to a
  subclass, which `main` does not do.
- **Recommendation:** Richards, then DeltaBlue: unannotated programs whose missing types a profile
  supplies, applied at build time as selective specialization was, with the mixed fields as the
  place where skew decides the representation. Not another dynamic site inside a typed program.

## 1. Why the drafts' candidates show little

Both drafts start from a program Pystachy already types and make one value dynamic:

| Draft | Dynamic value | What the static compiler already does | Result |
|---|---|---|---|
| #388 | `StringIO \| File` stream | union tag dispatch, inlinable per member | concrete AOT showed no consistent warm advantage |
| #389 | `Callable[[Record], int]` key | indirect call, callback not inlined | 1.79× warm, but every eligible callback is enumerated when the host is compiled; concrete AOT, the bound for a build-time guarded variant, takes 0.668 s whole-process against 0.992 s online |

Receiver dispatch on `main` behaves like #388's union. `tools/bench_receiver_dispatch.py` runs
`tools/fixtures/receiver_skew.py`, a plan of 1,000 constraints executed through `list[Constraint]`
with DeltaBlue's census skew (82/9/9 at `Plan.execute`), and a concrete control derived from it with
a `list[EqualityConstraint]` plan; the AST check asserts that no class or loop body changes.
Seven rotated samples, pinned to one CPU, 200,000 rounds each:

| Variant | ns per call, median | range |
|---|---:|---:|
| `list[Constraint]`, 82/9/9 mix | 1.654 | 1.611–1.766 |
| `list[Constraint]`, one class | 1.433 | 1.415–1.603 |
| `list[EqualityConstraint]` | 1.175 | 1.159–1.366 |

Paired ratios: one class over concrete **1.22×** (1.04–1.36); mix over concrete 1.41×, of which
1.14× is the mix itself, which a guarded specialization does not remove. The generic `execute`
has 6 class-tag compares, direct calls to 8 methods and no indirect call
([raw results](../benchmarks/receiver-dispatch.json)). The method bodies are one load and store,
so real ones dilute the dispatch share further.

## 2. Unannotated pyperformance on `main`

`tools/pyperformance_compile_census.py` reads the benchmarks from the pinned pyperformance 1.14.0
wheel, replaces each pyperf harness with one direct call, and builds the unchanged benchmark code
([raw results](../benchmarks/pyperformance-compile-census.json)):

| Benchmark | First error, unannotated | With recorded types |
|---|---|---|
| richards | types: `inheritance with generic class templates is not supported: annotate __init__ parameters` | 107 annotations; stops where `Task.__init__`'s `w` does not join (§3) |
| float | types: `__repr__ must return str` | 13 annotations; next, a local list built as `[None] * n` and filled later |
| deltablue | language: `class OrderedCollection(list)` is an unsupported base class | 131 annotations; same error; `Variable.value` int 3,754, float 4 |
| raytrace | module: `array` | not traced: no type fixes a module |
| chaos | module: `random` | not traced |
| go | module: `random` | not traced |

The census ranks the remaining blockers the same way: what Pystachy can express, not finding types.

## 3. Richards with recorded types

`tools/trace_annotate.py` runs the program under CPython with a profile hook and records the classes
of parameters, returns and fields (of `self`, of objects passed as arguments, of module-level objects
and of slots), reading no program code. Observations join as the typing reference does: `None` makes
a type optional, subclasses join to their nearest common base, and a call through a base annotation
must accept every override, so same-named methods of one hierarchy share one joined signature
(`fn(self, pkt: Packet | None, r: TaskRec) -> Task | None` for all five `fn`, including the base's,
which never runs). Positions that do not join are reported with their sample counts.

| Stage | Annotations | First error |
|---|---:|---|
| unannotated | 0 | `annotate __init__ parameters` (the task hierarchy) |
| recorded types | 107 | the same, at the one position left unannotated: `w` saw `Packet` 6, `None` 5, `int` 1 |
| two edits, recorded types | 112 | `'TaskRec' object has no attribute 'pending'` in `DeviceTask.fn` |

The two edits leave CPython's output unchanged, which the census tool checks:

| Edit | Why |
|---|---|
| `IdleTask(I_IDLE, 1, 10000, ...)` → `IdleTask(I_IDLE, 1, None, ...)` | `Task.input` is `Packet \| None` in every other task; the idle task never reads it |
| `BUFSIZE_RANGE = range(BUFSIZE)` → `list(range(BUFSIZE))` | a `range` kept in a global; it is only iterated |

The last error needs a compiler feature. Each task function receives its record through the joined
base type and reads subclass fields after `assert isinstance(d, DeviceTaskRec)`. On `main`,
`isinstance()` narrows optional values but not a base-typed value to a subclass, even in an `if`:
`tools/fixtures/isinstance_narrowing.py` fails with `'Base' object has no attribute 'extra'`.

## 4. Recommendation

**Richards first.** It is unannotated, unchanged apart from two labeled edits, and a classic
object-oriented benchmark. What blocks it is mostly types that a profile supplies, plus one
skewed mixed field. Its hot dispatch is the polymorphic inline cache case: the census puts 78% of
its calls at sites with two to four receiver classes, which Pystachy compiles as a type case.

**DeltaBlue next.** It tests "specialize higher up the call stack" directly: counted per caller's
argument types, the share of its calls that need one specialization rises from 36% to 95%, one of
the census's largest gains (+59 points, in a range of 48 to 69 across eight workloads), and its
busiest site is 82% one class. It needs subclassing of a
built-in (`list`), and a representation for `Variable.value`.

**Then raytrace,** whose census fields keep one type in only 12% of samples (integer and float
vector components), once `array` is available.

In order of the work they need:

1. `isinstance()` narrowing of a base-typed value to a subclass, in `if` and `assert`.
2. Recorded types applied where a compile error asks for an annotation, the piece
   [#264](https://github.com/den-run-ai/pystachy/issues/264) left open; `tools/trace_annotate.py`
   is a prototype, adding them all.
3. A representation for skewed mixed values: `Task.input`, `Variable.value`.
4. Subclassing of built-in classes, for DeltaBlue; local-variable types, for float's
   `[None] * n` list.

Apply profiles at build time first: no compiler runs while the program does (#389's online
compilation cost 0.327 s per process). Online specialization pays only when the skew changes with
the input.

## 5. Limitations

Each benchmark runs once, and recorded types describe the paths that run. The compiler reports its
first error only, so a stage's error says what blocks it next, not everything that does. The
annotator writes `ast.unparse` output, which drops comments. The receiver fixture's method bodies are
trivial, so its dispatch share is an upper bound.

## 6. Reproducing

```sh
make
python3 -m unittest discover -s tools -p test_trace_annotate.py
python3 tools/bench_receiver_dispatch.py --timing-cpu 2 --output build/receiver-dispatch/results.json
python3 -m pip download pyperformance==1.14.0 --no-deps -d build/pyperf
python3 tools/pyperformance_compile_census.py \
    --wheel build/pyperf/pyperformance-1.14.0-py3-none-any.whl \
    --output build/pyperformance-census/results.json
```

The census tool checks the wheel's SHA-256 and takes about 20 seconds; the receiver runs take about
10. Each result records the compiler, git head and status, and the input hashes.
