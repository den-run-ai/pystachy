# Coroutines

`async def` and `await` compile natively (PEP 492), and so do async generators (PEP 525) and
asynchronous comprehensions (PEP 530). A coroutine runs on the program's owner
thread, interleaving with others only where it awaits; nothing runs in parallel. This page
gives the supported forms, how they run, what they cost, how they relate to threads and
free-threaded CPython, and how the design compares with other implementations. The
[internals](internals.md#coroutines) describe the compiler's side.

## What compiles

| Form | Behavior |
|---|---|
| `async def f(...) -> R` | A call makes a coroutine object and runs none of the body. Its type is `Coroutine[Y, None, R]`: `Y` is what its awaits yield to the code that runs it, inferred from them (`None` until one yields something else), and `R` the annotation or what its returns return |
| `await x` | Runs `x` until it returns, yielding what `x` yields to the code that runs this coroutine; its value is what `x` returns. `x` is a coroutine, a generator of a `@types.coroutine` generator function, or an object whose `__await__` is a generator method |
| `await` of anything else | `TypeError: object int can't be used in 'await' expression`, as CPython raises it, also for a generator that `types.coroutine` does not mark; an `__await__` that is a `@types.coroutine` generator raises `TypeError: __await__() returned a coroutine` |
| A coroutine awaited again | `RuntimeError: cannot reuse already awaited coroutine`; one suspended where something else awaits it, `RuntimeError: coroutine is being awaited already` |
| `c.send(None)`, `c.throw(e)`, `c.close()` | Run, throw into or close `c` as a generator's methods do, through each await (PEP 380). A finished coroutine's `send()` and `throw()` raise `RuntimeError: cannot reuse already awaited coroutine`; a `StopIteration` that leaves one is `RuntimeError: coroutine raised StopIteration` |
| `Coroutine[Y, None, R]` | An annotation of a variable, parameter or field that holds coroutines (`typing`'s or `collections.abc`'s) |
| `async with A() as a, B() as b:` | Awaits `__aenter__()`, then `__aexit__()` as the block ends: with the exception that leaves it (`type, value, tb`), which a true result suppresses, or with `None, None, None` where the block ends, `break`s, `continue`s or `return`s (PEP 492) |
| `async for x in it: ... else: ...` | Calls `it.__aiter__()` once, then awaits its `__anext__()` for each item until that raises `StopAsyncIteration`, which ends the loop as exhaustion does (its `else` block runs) |
| An object without the protocol | CPython 3.13's `TypeError`s, such as `'X' object does not support the asynchronous context manager protocol (missed __aexit__ method)`, checked before `__aenter__()` runs, and `'async for' received an invalid object from __anext__: int` |
| `async def g(...)` that yields | An async generator function: a call makes an async generator object and runs none of the body. `async for`, `await anext(ag)` and `await ag.__anext__()` take its items until it finishes (`StopAsyncIteration`); its awaits pass what they yield on to the code that runs the coroutine that iterates it, and resume with what that sends. `try`/`finally`, `async with` and `async for` in it, also around a `yield` |
| `ag.asend(v)`, `ag.athrow(e)`, `ag.aclose()` | Awaitables of the next item: `asend()` sends `v` to the `yield` (an `AsyncGenerator[T, S]` annotation gives `S`), `athrow()` raises `e` there and gives what it yields next, `aclose()` raises `GeneratorExit` there and runs its `finally` blocks, awaits included, as CPython 3.13 does: `RuntimeError: anext(): asynchronous generator is already running` (and `athrow()`'s, `aclose()`'s) for a step while another is suspended, `cannot reuse already awaited __anext__()/asend()` (`aclose()/athrow()`) for an awaitable awaited again, `async generator ignored GeneratorExit`, and `async generator raised StopAsyncIteration` (or `StopIteration`) where one leaves the body |
| `AsyncGenerator[T, S]`, `AsyncIterator[T]`, `AsyncIterable[T]` | The return annotation of an async generator function or method (`async def __aiter__(self) -> AsyncIterator[int]`), and of a variable or field that holds async generators whose awaits yield `None` (`typing`'s or `collections.abc`'s); a function's parameter so annotated (not a method's) takes any async generator, and any object of a class with `__aiter__` |
| `aiter(x)`, `anext(it)`, `anext(it, default)` | `x.__aiter__()`, the awaitable of the next item, and one that gives `default` where the iterator raises `StopAsyncIteration`, for async generators and objects of classes with `__aiter__` and `__anext__`, with CPython's `TypeError`s for other objects |
| `[e async for x in it if c]`, `{...}`, `{k: v ...}` | Asynchronous comprehensions in an `async def`: `async for` clauses, first or later, mixed with `for` and `if` clauses, and `await` anywhere in them |
| `(e async for x in it)`, `(await f(x) for x in xs)` | An asynchronous generator expression: an async generator, also outside an `async def`; its first iterable and that iterable's `__aiter__()` are evaluated where it is written |
| Async methods overridden | A call through a base awaits whichever override the object's class has: their coroutines yield and return a joined type (a base that raises `NotImplementedError`, an override that returns an `int` and one that returns `None` make `int \| None`), so the overrides compile with that type from the start; results with no common type (an `int` and a `str`) stay an error, as for ordinary overrides |
| `import asyncio` | `asyncio.run()`, tasks, `gather()`, `sleep()`, `TaskGroup`, `timeout()`, `Lock`, `Event`, `Queue` and the event loop's callbacks and timers, adapted from CPython's pure-Python modules ([below](#how-asyncio-runs-tasks), [limits](../lib/compatibility.md#asyncio)) |

Nested `async def`s, `async def` methods and `@types.coroutine` generator functions compile
too. A driver loop such as pyperformance's `coroutines` benchmark runs unchanged:
[`bench/pyperformance/coroutines.py`](../bench/pyperformance/coroutines.py) adds only the
runner. [`tests/programs/upstream/upstream_coroutines.py`](../tests/programs/upstream/upstream_coroutines.py)
and [`upstream_coroutines_with_for.py`](../tests/programs/upstream/upstream_coroutines_with_for.py)
adapt 39 of CPython 3.13.16's `test_coroutines.py` cases, and list those they leave out;
[`upstream_asyncgen.py`](../tests/programs/upstream/upstream_asyncgen.py) adapts 18 of its
`test_asyncgen.py` cases that need no `asyncio` (its syntax cases are
`tests/errors/syntax/syntax_asyncgen_*.py`), and
[`upstream_coroutines_comp.py`](../tests/programs/upstream/upstream_coroutines_comp.py) its
`test_coroutines.py` asynchronous comprehension cases.

Not supported yet, each an error as the program compiles:

- a `for` loop over an async generator, and an `async for` clause of a comprehension over an
  object that is no asynchronous iterable, where CPython raises `TypeError` as the program runs;
  synchronous consumers of an asynchronous generator expression (`list(x async for x in it)`);
- `athrow(type, value, traceback)`, and an async generator's attributes (`ag_running`,
  `ag_frame`, `__name__`);
- most of `asyncio` beyond its event loop, tasks and primitives: sockets, streams,
  subprocesses, threads, `contextvars` and exception groups ([limits](../lib/compatibility.md#asyncio));
  CPython can also run a compiled [extension](concurrency.md#process-pools-today) from its own
  event loop;
- `send()` of a value other than `None`, `await` of a generator held in a variable, and an
  `__await__` that returns an iterator object instead of yielding;
- coroutines in containers that print or compare their items (`collections.deque` of
  coroutines compiles its `repr()`).

Deviations: a coroutine never awaited prints no `RuntimeWarning`, and one dropped while
suspended is not closed, as Pystachy finalizes no generator
([deviations](language/compatibility.md#memory-and-resource-lifetime)). The value a coroutine
returns is what `await` gives; its `StopIteration` carries none
(`tests/deviations/gen_stop_value.py`). A suspended async generator that the program drops is
not closed either: Pystachy has no `sys.set_asyncgen_hooks`, through which `asyncio` would
schedule its `aclose()`, and CPython without hooks closes it as its last reference goes
(`tests/deviations/agen_finalization.py`); an awaitable of its methods never awaited prints no
`RuntimeWarning`. The awaitables of `__anext__()`, `asend()`, `anext()`, `athrow()` and
`aclose()` are `async_generator_asend` and `async_generator_athrow` objects, as CPython's are,
but for `anext(ag, default)`'s, which CPython calls `anext_awaitable`; `throw()` of one that has
not started raises the exception at once, where CPython first checks that the async generator
is not running and then throws it into the async generator.

## How coroutines run

A coroutine is an LLVM switched-resume coroutine, as a [generator](internals.md#generators) is:
a stackless frame from the collected heap, whose suspension points are its awaits. `await`
resumes the awaitable directly (no exception carries its result), so a chain of awaits
resumes one frame per level, as CPython's does.

Recursive coroutines often never suspend, as in pyperformance's `coroutines`: every await in
them calls another such coroutine. Before compiling, Pystachy finds the module-level
`async def`s whose awaits are all calls, by name, of such `async def`s, and compiles
`await f(...)` of one as a plain call of `f`'s synchronous twin. No frame is allocated, nothing is resumed, and the result is what
running the coroutine would return, with the same exceptions; PEP 479's `RuntimeError` still
replaces a `StopIteration` leaving the twin. A call of `f` used as a value still makes a
coroutine. This is a static form of the fast paths that C#'s `ValueTask` and CPython 3.12's
eager tasks take at run time for work that completes without suspending.

pyperformance 1.14.0's `coroutines` runs `fibonacci(25)`, 242,785 coroutine calls, each of which
never suspends. In this [snapshot](benchmarks/pyperformance-coroutines-2026-11-12-0994130.json)
(`0994130`, five processes per mode on a shared 4-vCPU x86-64 host, CPython 3.13.18), the
median timed region of 50 calls took 0.915 s in CPython, 0.018 s in the JIT and 0.022 s in AOT,
about 40 to 50 times faster; its `generators` port, for comparison, ran 1.6 to 1.8 times faster.
A coroutine that does suspend pays a frame allocation for each call, and a resume of each
awaiting frame for each value it yields up the chain; there the twins do not apply. These are
noisy shared-host timings (the five AOT runs took 0.014 s to 0.024 s);
[`tools/bench_pyperformance.py`](../tools/bench_pyperformance.py) `--benchmarks coroutines`
measures the current tree.

`async with` and `async for` compile to the `try` and `while` statements that PEP 492 gives
for them, whose implicit awaits are ordinary awaits of `__aenter__()`, `__aexit__()` and
`__anext__()`: they cost what those awaits cost, and a coroutine suspended in one keeps its own
exception state while others run.

<a id="async-generators"></a>

## How async generators run

An async generator is one LLVM coroutine frame that suspends in two ways: at a `yield` of its
own, whose value is its consumer's, and where one of its awaits passes on what its awaitable
yields to the code that runs the consumer. A step of it (`await ag.__anext__()`, `anext()`,
`asend()`, `athrow()`, `aclose()`, `async for`) is code of the awaiting coroutine, not an
awaitable object: it resumes the frame, takes a yield of its own as its value, and where the
frame suspended in an await, suspends the awaiting coroutine with that value and resumes the
frame when it is resumed. Nothing is allocated for an item, and `async for` over an async
generator ends where it finishes without raising `StopAsyncIteration`, so an item costs what
an item of a `for` over a generator does: a resume, a suspension and a few loads and stores,
and one of each per level of a recursive chain such as `Tree.__aiter__()`. CPython instead
makes an `async_generator_asend` object for each step and wraps each value it yields. The
awaitables used as values (`a = ag.__anext__()`) are coroutine objects, each a frame allocation.
Asynchronous comprehensions take their items through the same steps.

pyperformance 1.14.0's `async_generators` traverses a balanced tree of 100,000 nodes through
recursive `async for` loops in `Tree.__aiter__()`, building the tree in the timed region as
upstream does; [`bench/pyperformance/async_generators.py`](../bench/pyperformance/async_generators.py)
runs it with `send(None)` where pyperf uses an `asyncio` event loop, since nothing in it suspends.
In this [snapshot](benchmarks/pyperformance-async-generators-2026-11-12-226de94.json) (`226de94`,
five processes per mode on a shared 4-vCPU x86-64 host whose load average was about 1, CPython
3.13.18), the median timed region of three runs (each builds and traverses a tree) took 0.804 s in CPython, 0.088 s in the JIT
and 0.071 s in AOT, about 9 and 11 times faster; the `generators` port, whose tree is the same
with `yield from`, ran 1.5 and 1.7 times faster in the same measurement: CPython's step of an
async generator costs much more than its resume of a generator. `--benchmarks async_generators` of
[`tools/bench_pyperformance.py`](../tools/bench_pyperformance.py) measures the current tree.

<a id="how-asyncio-runs-tasks"></a>

## How asyncio runs tasks

`lib/asyncio` is CPython 3.13.16's pure-Python event loop, `Future` and `Task` (`_PyFuture`,
`_PyTask`), typed, with marked edits. A coroutine's yield type is one static type, so every
awaitable of the module yields `None`, where CPython's `Future.__await__()` yields the future
itself to the task: awaiting a pending future records it, the coroutine suspends, and the task's
`__step()` takes the future recorded and waits on it with CPython's own logic (a done callback
that wakes the task, cancellation of the future it waits on); a bare yield (`sleep(0)`)
reschedules the task. `Future[T]` and `Task[T]` derive from a `_FutureBase` without `T`, which
the loop, `gather()` and `TaskGroup` hold, so a program's tasks of different result types share
one loop; that is what generic classes with a base, `None` as a type argument (a
`Future[None]`, a `list[None]` from `gather()`) and a list unpacked into `*args`
(`gather(*coros)`) were added for. A task runs a small coroutine that awaits the program's and
keeps its result, since a coroutine's `StopIteration` carries no value here. When nothing is
ready, the loop sleeps until its next timer.

A task costs two coroutine frames (the program's and the one that keeps its result), a
`Task` object with its result list, a `Handle` and a function of no arguments for each step
scheduled, and a resume of each awaiting frame per step; awaits of coroutines that never
suspend stay plain calls of their twins. pyperformance 1.14.0's `async_tree` gathers a tree of
six levels of six branches (55,987 coroutines per run; 46,656 leaves) with `gather()` or task
groups, with the eager task factory or not, where the leaves do nothing (`none`), sleep 50 ms
(`io`), sleep unless memoized (`memoization`), or compute or sleep (`cpu_io_mixed`).
[`bench/pyperformance/async_tree.py`](../bench/pyperformance/async_tree.py) runs each variant.
The table gives the median timed region of five processes per mode, each running the variant
once and printing what CPython prints: CPython 3.13.18 with its C `_asyncio`, CPython with
`_asyncio` blocked, which leaves the pure-Python `Future` and `Task`, and Pystachy's JIT and AOT,
on a shared 4-vCPU x86-64 host whose load average was 0.4 to 1.0. The
[recorded samples](../bench/pyperformance/results/async-tree-2026-11-12.json) give the commit,
commands and every sample:

| Variant | Tasks | CPython | CPython, pure-Python `Task` | JIT | AOT | CPython / JIT | CPython / AOT |
|---|---|---:|---:|---:|---:|---:|---:|
| `none` | `gather()` | 0.342 s | 0.650 s | 0.139 s | 0.117 s | 2.5x | 2.9x |
| `none` | `TaskGroup` | 0.310 s | 0.676 s | 0.125 s | 0.123 s | 2.5x | 2.5x |
| `io` | `gather()` | 0.881 s | 1.657 s | 0.258 s | 0.235 s | 3.4x | 3.7x |
| `io` | `TaskGroup` | 0.860 s | 1.720 s | 0.233 s | 0.226 s | 3.7x | 3.8x |
| `memoization` | `gather()` | 0.532 s | 0.877 s | 0.164 s | 0.164 s | 3.2x | 3.3x |
| `memoization` | `TaskGroup` | 0.499 s | 0.819 s | 0.165 s | 0.158 s | 3.0x | 3.2x |
| `cpu_io_mixed` | `gather()` | 1.463 s | 1.774 s | 0.270 s | 0.228 s | 5.4x | 6.4x |
| `cpu_io_mixed` | `TaskGroup` | 1.510 s | 1.864 s | 0.278 s | 0.230 s | 5.4x | 6.6x |
| `eager` | `gather()` | 0.095 s | 0.218 s | 0.076 s | 0.069 s | 1.2x | 1.4x |
| `eager` | `TaskGroup` | 0.271 s | 0.462 s | 0.105 s | 0.095 s | 2.6x | 2.9x |
| `eager_io` | `gather()` | 1.063 s | 1.770 s | 0.259 s | 0.232 s | 4.1x | 4.6x |
| `eager_io` | `TaskGroup` | 0.982 s | 1.699 s | 0.259 s | 0.219 s | 3.8x | 4.5x |
| `eager_memoization` | `gather()` | 0.241 s | 0.590 s | 0.143 s | 0.135 s | 1.7x | 1.8x |
| `eager_memoization` | `TaskGroup` | 0.356 s | 0.776 s | 0.143 s | 0.156 s | 2.5x | 2.3x |
| `eager_cpu_io_mixed` | `gather()` | 1.276 s | 1.462 s | 0.246 s | 0.216 s | 5.2x | 5.9x |
| `eager_cpu_io_mixed` | `TaskGroup` | 1.387 s | 1.779 s | 0.259 s | 0.211 s | 5.4x | 6.6x |

Without the eager task factory, the compiled tasks ran 2.5 to 3.8 times faster than CPython's C
`Task` (5.4 to 6.6 times in the `cpu_io_mixed` variants, whose ported factorial is less work than
CPython's big-int one, see the [adaptation notes](../bench/pyperformance/README.md)). The eager
factory runs a new task's first step at once, so leaves that never suspend finish without being
scheduled, and the gap narrows: 1.7 to 2.9 times in `eager_memoization` and in `eager` with task
groups, and only 1.2 (JIT) and 1.4 (AOT) times in `eager` with `gather()`. Against CPython
running the same pure-Python `Task`, the compiled code ran 4.1 to 8.4 times faster, and 2.9 to
4.9 times in the `eager` variant. These are shared-host timings of one tree;
[`tools/bench_pyperformance.py`](../tools/bench_pyperformance.py) `--benchmarks async_tree`
measures its `none` variant on the current tree.

## Threads, parallelism and free-threading

A Pystachy runtime has one [owner thread](concurrency.md#ownership), and coroutines are
objects of its heap. Concurrency is cooperative: a coroutine runs until its next await, so code
between two awaits is never interleaved with another task's. `asyncio` programs rely on that
atomicity, and Pystachy keeps it because a coroutine suspends only at an await.

- **Blocking.** A blocking call in a coroutine blocks every task of the thread, as in CPython.
  Compiled code cannot run on another thread, so `asyncio.to_thread()` has no native
  equivalent; CPython can await compiled exports in a
  [process pool](concurrency.md#process-pools-today).
- **Parallelism.** Coroutines give none. Separate processes do today; native parallel
  kernels are tracked in [#714](https://github.com/den-run-ai/pystachy/issues/714).
- **Free-threaded CPython.** With PEP 703 (experimental in 3.13, supported in 3.14), the
  event loops of different threads run in parallel; a coroutine still belongs to the loop that
  runs it, and resuming one that is running raises `ValueError: coroutine already executing`. Pystachy's equivalent check
  reads a state word without atomics. Shared-heap threads would need an atomic transition of
  that word on every resume, a collector that coordinates every thread whose frames or
  suspended coroutines hold references, and one loop per thread rather than locks around the
  coroutine machinery.
- **Extension modules.** A compiled extension refuses calls from any thread but its importer
  ([threading contract](ffi.md#threading-and-host-lifetime)), so CPython's event loop thread
  may call it, and its executors' threads may not.

## Design notes

| Implementation | Approach | What Pystachy takes from it |
|---|---|---|
| CPython 3.11+ | A coroutine embeds its frame, and the specialized `SEND` resumes an awaited coroutine's frame in the same interpreter loop; 3.12's eager task factory runs a task synchronously until it first suspends | CPython's messages and states; the eager idea as compile-time twins |
| PyPy, GraalPy | JIT-compiling interpreters: a suspended frame lives on the heap, and speed depends on the JIT optimizing through resumes after warmup. PyPy also offers stackful greenlets | Avoid frames on the hot path rather than make them cheap |
| MicroPython | Stackless generator-based coroutines; its `asyncio` keeps a small native core (tasks and a pairing-heap queue) under a Python API | A future native event loop: small core, library API |
| mypyc, Cython, Nuitka | An `async def` becomes a native coroutine object whose resume switches on a saved label; an await of their own coroutines can skip the generic protocol, but each call still allocates | LLVM's coroutine passes provide the state machine; twins also remove the allocation |
| C++20, LLVM | Stackless coroutines; heap allocation elision (HALO, CoroElide) when a coroutine's lifetime nests in its caller's; symmetric transfer, which resumes the next coroutine by a tail call | Pystachy destroys an awaited coroutine where it returns, so that CoroElide may elide its frame; resuming the innermost awaited coroutine directly is future work |
| Rust | `async fn` compiles to a state machine that embeds the futures it awaits; recursion needs a box; executors (tokio) steal work across threads under `Send` bounds | Static layout pays off; thread safety must be part of the type, not a run-time check |
| C#, Kotlin | Allocation-free synchronous completion (`ValueTask`); CPS with a `COROUTINE_SUSPENDED` marker that lets a non-suspending call return directly | The same goal as twins, decided per call at run time |
| Go | Stackful goroutines with small growable stacks, an M:N scheduler with per-processor run queues and work stealing, an integrated network poller, preemption; no `async` coloring | Integrated I/O polling and a run queue for a native event loop; not preemption, which would break atomicity between awaits, nor stack switching, which the collector and C calls would have to follow |

Go's design trades explicit suspension points for cheap stack switching: any call may block
and the runtime parks the goroutine. Python's `await` marks every suspension point, which is
what makes a stackless design sufficient and keeps CPython's semantics; Java's virtual threads
and OCaml 5's effects show that stackful designs need runtime support for every frame and
foreign call that a task may hold.
