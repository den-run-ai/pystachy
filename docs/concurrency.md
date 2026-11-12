# Concurrency contract

Each Pystachy runtime runs on one owner thread. To run compiled work in parallel,
use CPython to start separate processes, each importing an
[extension module](ffi.md#extension-modules) built with `pystachy ext`.
The [process-pool example](#process-pools-today) below shows this arrangement.

This page describes current behavior and the probes that check it. Native
parallel loops, shared-heap threads and `async def` remain unsupported; their
proposals are linked under [design history](#design-history).

## Capabilities

**Native** means the compiled runtime provides the operation; extension modules
are built ahead of time. **Hosted** means CPython provides it, calling compiled
exports or embedded through
[`pyobj`](ffi.md#calling-cpython). **Refused** means the operation raises before
changing runtime state. The comparison baseline is CPython 3.13.16, pinned in
[`.python-version`](../.python-version).

Every row names registered probes. Lint runs
[`tools/test_concurrency_contract.py`](../tools/test_concurrency_contract.py)
to check that the probes exist and that their test suites execute them.

| Capability | Status | Probes |
|---|---|---|
| Calls into an extension module from the thread that imported it | native | `tests/ffi/ext/client.py`, `tests/ffi/ext/pwclient.py` |
| Calls from any other thread: `threading.Thread`, `ThreadPoolExecutor`, `asyncio.to_thread()`, `loop.run_in_executor(None, ...)` | refused: `RuntimeError` before the call converts an argument; the owner's next call works | `tests/ffi/ext/client.py`, `tests/ffi/ext/pwclient.py`, `tests/ffi/ext/aioclient.py` |
| `multiprocessing.Pool` (spawn) mapping an export | hosted | `tests/ffi/ext/pk3.py` |
| `ProcessPoolExecutor` (spawn): two workers at once, each with its own runtime; results, exceptions and `SystemExit`; shutdown; a worker killed in a compiled call | hosted | `tests/ffi/ext/pwclient.py` |
| `multiprocessing.Process` with an export as its target: `SystemExit`'s code is the exit status | hosted | `tests/ffi/ext/pwclient.py` |
| `asyncio` awaiting exports in a process pool: the loop runs meanwhile; a timeout or a cancelled task stops the waiting, not a call that a worker has started or that the executor has dispatched to its call queue; a call still pending in the executor is cancelled | hosted | `tests/ffi/ext/aioclient.py` |
| A compiled program running `subprocess` and `multiprocessing.Pool` through embedded CPython | hosted | `tests/ffi/py_exe.py` |
| Generators as LLVM coroutines, whose suspended frames the collector scans | native | `tests/programs/generators/`, run under GC stress |
| `select.select()` readiness on integer descriptors | native | `tests/programs/library/lib_select.py`, `tools/selectprobe.c` |
| `_thread` locks, reentrant locks and thread identities, in the one thread | native | `tests/programs/library/lib_thread.py` |
| `_thread.start_new_thread()` | refused: `NotImplementedError` | `tests/deviations/lib_thread_start.py` |
| `threading`'s locks, conditions, semaphores, events, barriers, timers and `Thread` objects, in the one thread | native | `tests/programs/library/lib_threading.py` |
| `threading.Thread.start()` | refused: `NotImplementedError` | `tests/deviations/threading_start.py` |
| A lock `acquire()` or a `join()` that would wait forever | refused: `RuntimeError` | `tests/deviations/lib_thread_deadlock.py` |
| `async def`, `await`, `async for`, `async with` | refused at compile time | `tests/errors/generators/gen_async.py` |


A compiled program cannot import `queue`, `asyncio`, `concurrent.futures`,
`multiprocessing`, `contextvars`, `selectors`, `socket` or `signal`;
use the hosted interfaces for those operations. Native process control provides
[`subprocess`](../lib/compatibility.md#subprocess), `os.system()` and `os.execv()`, with no
`os.fork()` or `os.pipe()`. `_thread` and
`threading` run only on the owner thread: importing them does not enable
`Thread.start()`.

The optional [`netio` example](../examples/netio/README.md) prototypes native
IPv4 TCP, local socket pairs and epoll/kqueue readiness through a separate C
bridge. It runs under CPython and Pystachy with explicit resource ownership and
compares its bounded API with the real stdlib. Its pipe consumer drains inherited
worker output with deadlines; the launcher owns worker processes. This does not
enable native stdlib `socket`, `selectors` or `asyncio` imports.

An `abi3t` extension refuses import under `PYTHON_GIL=0`. That check needs a
free-threaded CPython 3.15, which CI does not run. See the
[extension threading and host-lifetime contract](ffi.md#threading-and-host-lifetime).

## Process pools today

Create `work.py` with an exported function:

```python
from ffi import export


@export
def score(n: int) -> int:
    return n * n
```

Build the extension:

```sh
./pystachy ext work.py
```

Save the following as `pool.py` beside the built extension, then run it with
`python3.13 pool.py`. CPython runs the orchestrator; each worker imports and calls
the compiled module.

```python
import asyncio
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

import work


async def main():
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(4, mp_context=mp.get_context("spawn")) as pool:
        pending = [loop.run_in_executor(pool, work.score, n) for n in range(100)]
        scores = await asyncio.gather(*pending)
    print(sum(scores))


if __name__ == "__main__":
    asyncio.run(main())
```

The program prints `328350`. Spawn imports the main script in every worker, so
the `__main__` guard is required. Each worker initializes its own copy of `work`
once. The event-loop thread also owns a copy and may call `work.score()` directly,
but a direct call blocks that loop until it returns.

## Guarantees

### Ownership

Each runtime has one owner: a program's main thread, or the thread that imported
an extension module. Calls from another thread raise `RuntimeError` before
converting arguments or running module code. Later calls from the owner still
work.

Each process, and each extension module within a process, has its own runtime and
heap. Values cross between modules as Python-object copies and between processes
as serialized values. Compiled code does not share a managed heap across threads.

### Processes

Use `spawn` or a process exec. Do not fork a process that runs or may run threads;
CPython 3.13 defaults to fork on Linux, so select the start method explicitly.
An export pickles by name, with `int`, `float`, `bool` or `str` arguments and one
of those types or `None` as its result. `loop.run_in_executor(None, ...)` chooses
threads; pass a process executor as in the example.

| Event | `ProcessPoolExecutor` behavior |
|---|---|
| Normal return | The future contains the result. |
| Compiled exception | The future raises the builtin exception class, or the nearest builtin base of a module-defined exception. |
| `SystemExit` | The future raises `SystemExit`. |
| Worker lost during a call | The call and pending calls fail with `BrokenProcessPool`. |
| Timeout or cancelled waiter | Waiting stops; an already dispatched or started call continues. |
| `Future.cancel()` | Cancels a still-pending call; returns `False` once the executor has dispatched it, even if no worker has entered it yet. |

`multiprocessing.Pool` replaces a dead worker but never completes the call that
worker was running. The same happens if an export raises `SystemExit` in its
worker. Use `AsyncResult.get(timeout)` to bound the wait, or choose
`ProcessPoolExecutor`, which reports these failures.

A timeout alone does not stop a worker or bound executor shutdown. A result that
was not cancelled can still be collected. If a worker is lost, whether its call
completed is unknown; retry only with an explicit policy and an idempotent call.
The orchestrator owns limits on outstanding work and recovery.

### Sequential performance

A program that uses no concurrency starts no thread or worker pool. Programs
link libc and libm, plus libdl only for the FFI; they require no thread or OpenMP
library. Object headers and the allocator perform no atomic operations.

## Writing concurrency tests

- Control interleavings with barriers, events and semaphores. If no signal exposes
  a state, such as executor dispatch, poll it with a bound.
- Bound every wait and the whole client. The probes use 30-second waits;
  [`pwdeadline.py`](../tests/ffi/ext/pwdeadline.py) kills and reaps a client's
  children after its deadline. A future timeout alone is insufficient because
  `ProcessPoolExecutor.__exit__()` waits for unfinished work.
- Hold a call that kills its worker until all calls expected to fail have been
  submitted. An earlier death can break the pool during the next `submit()`.
- Check permitted results and failures. Which worker runs a call, and how many
  calls each worker takes, are not contractual.
- Make clients check their own output and exit nonzero on failure.
  [`tests/ffi/run.sh`](../tests/ffi/run.sh) requires source and extension runs to
  agree and both to exit successfully.
- Register new probes in the capability table and in an executed test suite.

<a id="asynchronous-execution-proposed"></a>
<a id="atomics"></a>
<a id="library-stages"></a>
<a id="memory-visibility"></a>
<a id="parallel-loops-proposed"></a>
<a id="reusing-llvm"></a>

## Design history

Native parallel loops are tracked in [#714](https://github.com/den-run-ai/pystachy/issues/714),
async execution in [#12](https://github.com/den-run-ai/pystachy/issues/12), and the
broader concurrency design in [#754](https://github.com/den-run-ai/pystachy/issues/754).
The proposed worker, memory-visibility, atomic and LLVM-backend requirements remain
in the [earlier design](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/docs/concurrency.md),
with sequential-equivalence and effect-safety work in
[#409](https://github.com/den-run-ai/pystachy/issues/409) and
[#702](https://github.com/den-run-ai/pystachy/issues/702). These proposals do not
add capabilities to the current table.
