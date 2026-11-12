# Coroutines

`async def` and `await` compile natively (PEP 492). A coroutine runs on the program's owner
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

Nested `async def`s, `async def` methods and `@types.coroutine` generator functions compile
too. A driver loop such as pyperformance's `coroutines` benchmark runs unchanged:
[`bench/pyperformance/coroutines.py`](../bench/pyperformance/coroutines.py) adds only the
runner. [`tests/programs/upstream/upstream_coroutines.py`](../tests/programs/upstream/upstream_coroutines.py)
and [`upstream_coroutines_with_for.py`](../tests/programs/upstream/upstream_coroutines_with_for.py)
adapt 39 of CPython 3.13.16's `test_coroutines.py` cases, and list those they leave out.

Not supported yet, each an error as the program compiles:

- asynchronous comprehensions (`[x async for x in it]`) and async generators (an `async def`
  that yields); `await` in an ordinary comprehension compiles;
- the `asyncio` module, which is not shipped (CPython can run a compiled
  [extension](concurrency.md#process-pools-today) from its own event loop);
- `send()` of a value other than `None`, `await` of a generator held in a variable, and an
  `__await__` that returns an iterator object instead of yielding;
- coroutines in containers that print or compare their items (`collections.deque` of
  coroutines compiles its `repr()`).

Deviations: a coroutine never awaited prints no `RuntimeWarning`, and one dropped while
suspended is not closed, as Pystachy finalizes no generator
([deviations](language/compatibility.md#memory-and-resource-lifetime)). The value a coroutine
returns is what `await` gives; its `StopIteration` carries none
(`tests/deviations/gen_stop_value.py`).

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
