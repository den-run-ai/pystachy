# Concurrency contract

This page is the execution contract for concurrency: what holds today, the guarantees that
later features must keep, and the probes that check them. It specifies observable behavior;
schedulers, threading backends and object representations remain free to change. Today each
runtime runs on one thread, and parallel work runs in separate processes that CPython starts
and that import [extension modules](reference/ffi.md#extension-modules) compiled by
`pystachy ext`. Native parallel loops ([#714](https://github.com/den-run-ai/pystachy/issues/714))
and `async def` ([#12](https://github.com/den-run-ai/pystachy/issues/12)) are proposals, not
features. [#754](https://github.com/den-run-ai/pystachy/issues/754) records the evidence behind
this contract and tracks its plan.

The ground rule is [#409](https://github.com/den-run-ai/pystachy/issues/409)'s: a concurrency
feature never changes what a correctly compiled program does. Where a parallel or asynchronous
execution cannot be shown to give the sequential result, the sequential code runs.

## Capabilities

**Native** means compiled code does it, in JIT and AOT. **Hosted** means CPython does it, calling
compiled exports or embedded through [`pyobj`](ffi.md#calling-cpython). **Refused** means an
error, raised before the runtime's state changes. Each row names the registered tests that check
it, which `tools/test_concurrency_contract.py` (run by Lint) requires to exist and to be run by
their suite. The baseline is the CPython of [`.python-version`](../.python-version), 3.13.16.

| Capability | Status | Probes |
|---|---|---|
| Calls into an extension module from the thread that imported it | native | `tests/ffi/ext/client.py`, `tests/ffi/ext/pwclient.py` |
| Calls from any other thread: `threading.Thread`, `ThreadPoolExecutor`, `asyncio.to_thread()`, `loop.run_in_executor(None, ...)` | refused: `RuntimeError` before the call converts an argument; the owner's next call works | `tests/ffi/ext/client.py`, `tests/ffi/ext/pwclient.py`, `tests/ffi/ext/aioclient.py` |
| `multiprocessing.Pool` (spawn) mapping an export | hosted | `tests/ffi/ext/pk3.py` |
| `ProcessPoolExecutor` (spawn): two workers at once, each with its own runtime; results, exceptions and `SystemExit`; shutdown; a worker killed in a compiled call | hosted | `tests/ffi/ext/pwclient.py` |
| `multiprocessing.Process` with an export as its target: `SystemExit`'s code is the exit status | hosted | `tests/ffi/ext/pwclient.py` |
| `asyncio` awaiting exports in a process pool: the loop runs meanwhile; a timeout or a cancelled task stops the waiting, not started work; unstarted work is cancelled | hosted | `tests/ffi/ext/aioclient.py` |
| A compiled program running `subprocess` and `multiprocessing.Pool` through embedded CPython | hosted | `tests/ffi/py_exe.py` |
| Generators as LLVM coroutines, whose suspended frames the collector scans | native | `tests/programs/generators/`, run under GC stress |
| `select.select()` readiness on integer descriptors | native | `tests/programs/library/lib_select.py`, `tools/selectprobe.c` |
| `_thread` locks, reentrant locks and thread identities, in the one thread | native | `tests/programs/library/lib_thread.py` |
| `_thread.start_new_thread()` | refused: `NotImplementedError` | `tests/deviations/lib_thread_start.py` |
| A lock `acquire()` or a `join()` that would wait forever | refused: `RuntimeError` | `tests/deviations/lib_thread_deadlock.py` |
| `async def`, `await`, `async for`, `async with` | refused at compile time | `tests/errors/generators/gen_async.py` |

A compiled program cannot import `threading`, `queue`, `asyncio`, `concurrent.futures`,
`multiprocessing`, `subprocess`, `contextvars`, `selectors`, `socket` or `signal`: the compiler
reports that the module is not supported. Of process control it has `os.system()` and
`os.execv()`, with no `fork`, pipe or spawn. Importing a module is not functional support:
`_thread` imports and runs one thread. An `abi3t` module refuses import under `PYTHON_GIL=0`;
that check needs a free-threaded CPython 3.15, which CI does not run.

`multiprocessing.Pool` replaces a worker that dies, but never completes the call that the worker
was running, and the same happens when an export raises `SystemExit` in a pool's worker: wait
with a timeout (`AsyncResult.get(timeout)`), or use `ProcessPoolExecutor`, which reports both.

Proposed capabilities, each to add a row above with the probes listed here:

| Capability | Tracker | Its probes show |
|---|---|---|
| Parallel loops over numeric lists (`prange`, whose CPython twin is `range`) | [#714](https://github.com/den-run-ai/pystachy/issues/714), after [#702](https://github.com/den-run-ai/pystachy/issues/702) | the `range` loop's results, exceptions and writes; aliased and overlapping lists; bounds and overflow failures at the same iteration, after the same writes; GC stress around joins; ThreadSanitizer |
| `async def`, `await`, `asyncio.run()`, `create_task()`, `sleep()`, tasks and futures | [#12](https://github.com/den-run-ai/pystachy/issues/12) | lazy coroutine creation, timer progress, results and errors, cancellation that runs `finally`, GC stress across suspension |
| `contextvars`, a bounded `asyncio.Queue`, `Lock` and `Event` | with tasks | context isolation, backpressure, cancelled waiters removed |
| A `selectors` subset, nonblocking pipes and sockets | with native I/O | a producer and a consumer driven by readiness, never blocking the loop |
| Threads that share one heap: `threading`, `queue`, `ThreadPoolExecutor`, subinterpreters | later, for a concrete workload | registered stacks and roots, per-thread exception state, synchronized allocation, every container and cache audited |

## Guarantees

### Ownership

- Each runtime has one owner thread: a program's main thread, or the thread that imported an
  extension module. A call from another thread is refused before it converts an argument or runs
  any of the module's code, and the owner's later calls work.
- Each process, and each extension module in a process, has its own runtime and heap. Values
  cross between them only as copies: Python objects, or serialized bytes between processes.
- The native workers of a parallel region (proposed) read and write only validated numeric
  buffers that the owner keeps alive until the join. They do not allocate, collect, raise, do I/O
  or call user code.
- Ownership extends to other threads only through audited synchronization of everything that a
  runtime shares (the last proposed capability above).

### Parallel loops (proposed)

- A parallel loop gives the sequential loop's results, exceptions and writes. Its eligibility is
  proven; otherwise the original loop runs sequentially. A programmer's promise of independence
  is not proof, since a wrong one would give results that the CPython twin does not.
- The first phase excludes reductions, allocation, callbacks, I/O and every operation that may
  raise: a loop that may raise runs sequentially, so that it raises where CPython does, after the
  same writes. Integer reductions need an overflow proof. Float reductions keep their sequential
  order, since reassociation changes rounding.
- Effect summaries are not enough. `len()` of a `str` has an empty summary but caches the string's
  code-point count, and a `dict[str, int]` lookup caches the key's hash
  ([#754](https://github.com/den-run-ai/pystachy/issues/754)). Eligibility needs its own
  worker-safety classification: an allowlist of runtime helpers and IR operations, reviewed
  through everything they call, with alias and overlap checks, lifetime protection, and bounds
  and overflow proofs ([#702](https://github.com/den-run-ai/pystachy/issues/702)). A new or
  unknown helper is ineligible until reviewed. The classification decides only whether a loop
  runs in parallel; it never rejects a program.
- Nested regions run sequentially. One CPU budget per process bounds the workers and accounts for
  BLAS threads and process workers.
- The serial implementation of the parallel entry point stays the default and the reference; a
  pthread or libomp backend is optional.

### Memory visibility

- Starting a parallel region publishes the owner's writes to its workers; the join publishes the
  workers' writes to the owner before it continues. A parallel loop is not a transaction.
- Ordinary Python operations gain no atomicity: `x += 1` stays a read, an addition and a write.
  Compound state shared between threads needs a lock.

### Asynchronous execution (proposed)

- A coroutine resumes only on its owner thread, never while a parallel region runs, and its
  suspended frame stays a collector root, as a generator's does today.
- Each task keeps its own exception state and context.
- Cancellation is cooperative: it arrives at an `await`, and its supported paths run `finally`
  blocks and context managers' exits.
- There is no preemption, and no promise that a given `await` lets another task run.
- One event loop thread waits on readiness (`select.select()` first); native completions reach it
  through a queue, and helper threads never allocate.

### Atomics

- The runtime has no inter-thread atomics today. Its signal flags are `volatile sig_atomic_t`,
  correct for a handler on the thread it interrupts and for nothing else.
- Atomics start inside the runtime, for the parallel runtime's counters and flags: C11 atomics
  compiled by LLVM, sequentially consistent until a weaker order is measured and reviewed, and
  never on object headers or managed pointers.
- A public atomic integer, if one is added, is sequentially consistent by default and keeps
  Pystachy's checked arithmetic: an overflow raises `OverflowError`. LLVM's `atomicrmw add` wraps,
  so this needs a compare-and-swap loop.
- `volatile` is not synchronization. Lock-free execution is not a portability guarantee.

### Processes

- Workers have separate heaps and exchange explicit serialized values. An export pickles by name;
  its arguments and results are `int`, `float`, `bool`, `str` or `None`.
- Workers start with `spawn` (or a process exec), never by `fork` from a process that runs or may
  run threads. CPython 3.13 forks by default on Linux, so name the start method.
  `loop.run_in_executor(None, ...)` uses threads: give it a process executor.
- With `ProcessPoolExecutor`, a call reports its result or its failure. A worker's exception
  arrives as the builtin class that the export raised (a class of the module's own as its nearest
  builtin base), `SystemExit` as itself, and a lost worker as `BrokenProcessPool` for its call and
  for each pending one. `multiprocessing.Pool` reports neither of the last two (above).
- A timeout means that the caller stopped waiting. Work that a worker has started runs to
  completion (`Future.cancel()` returns `False`), and its result can still be collected; only
  work that no worker has started can be cancelled.
- A lost worker leaves its call's completion unknown: a retry needs an explicit policy and an
  idempotent call. Bounding outstanding work, identifying tasks, placement and recovery belong
  to the orchestrating framework.

### Sequential performance

- Concurrency is opt-in. A program that uses none starts no thread or worker pool, links no
  thread or OpenMP library (programs link libc and libm, and libdl only for the FFI), and runs no
  atomic operation on an object header or in the allocator.
- The first native concurrency feature adds the probe for this: unchanged IR and linkage for
  programs that do not use it (`make irsame REF=<base>`), a check of the runtime's IR and of the
  executables' libraries, and measurements against its base.

## Reusing LLVM

LLVM supplies mechanisms; the Python semantics stay Pystachy's.

- **Coroutines:** generators already lower to LLVM's switched-resume coroutines, and CoroSplit and
  CoroElide lay out and elide their frames ([internals](internals.md#generators)). Tasks reuse that
  lowering; scheduling, cancellation and root ownership stay in the runtime.
- **Atomics:** C11 atomics in the runtime's C, which LLVM lowers. Their runtime entries carry the
  `I` effect, so that the compiler's own passes do not move them.
- **Parallel regions:** one runtime entry point, conceptually
  `pys_parallel_for(start, stop, grain, kernel, context)`, with a serial implementation behind it
  and an optional pthread or libomp backend. `tools/setup.sh` installs no OpenMP runtime, and
  without one `clang -fopenmp` cannot find `-lomp`.
- LLVM provides no collector and no thread coordination: statepoints assume that something else
  places safepoints.

## Library stages

| Stage | CPython APIs | Acceptance |
|---|---|---|
| Now, hosted | `multiprocessing` with an explicit spawn context (`Pool`, `Process`); `ProcessPoolExecutor` (`submit()`, `map()`, results and exceptions, `cancel()`, `shutdown()`); `asyncio.run()` awaiting a process executor; `subprocess` through embedded CPython | the probes above |
| Next, native async | `async def`, `await`, `asyncio.run()`, `create_task()`, `sleep()`, task and future completion and cancellation; monotonic timers over `select.select()` | lazy coroutines, timers, propagation, cancellation and cleanup |
| With tasks | `contextvars`, a bounded `asyncio.Queue`, selected `Lock` and `Event` operations | context isolation, backpressure, cancelled waiters removed |
| With native I/O | a documented `selectors` subset; the nonblocking pipe and socket operations that one real application needs | readiness-driven producer and consumer |
| Later | `threading`, `queue`, `ThreadPoolExecutor`, subinterpreters | the shared-heap work first |

## Process pools today

CPython runs the program; `work.py` is compiled with `pystachy ext work.py`:

```python
import asyncio
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import work


async def main():
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(4, mp_context=mp.get_context("spawn")) as pool:
        scores = await asyncio.gather(*(loop.run_in_executor(pool, work.score, n) for n in range(100)))
    print(sum(scores))


if __name__ == "__main__":
    asyncio.run(main())
```

Each worker imports the module itself and runs its code once. Spawn imports the main script in
every worker, hence the `__main__` guard. The loop's thread imported `work`, so it may also call
`work.score()` directly, blocking the loop meanwhile.

## Writing concurrency tests

- Control interleavings with barriers, events and semaphores, not with sleeps, and bound every
  wait (60 seconds in the probes) so that a broken handshake fails rather than hangs.
- Check what the contract permits, not an incidental schedule: which worker ran a call, or how
  many calls each took, is not part of it.
- A client checks its own lines and exits nonzero when one is wrong: `tests/ffi/run.sh` requires
  its runs with the source and with the extension to agree and to exit with status 0.
- Each native feature adds JIT and AOT differential cases for aliasing, overlap, bounds, overflow
  and partial writes; `PYSTACHY_GC_STRESS_PROGRAM=1` across suspension and joins; cancellation,
  context isolation and bounded-queue cleanup; ThreadSanitizer over its workers and the runtime;
  unchanged IR and linkage for the programs that do not use it; and its row of the capability
  table.
