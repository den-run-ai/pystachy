# CPython's asyncio awaiting compiled exports in a process pool whose workers start by spawn
# (docs/concurrency.md): the event loop runs while a worker holds a call; results and exceptions
# come back through await; a timeout or a cancelled task stops the waiting, not a call that a worker
# has started or that the executor has dispatched to its call queue, and a cancelled task's call
# still pending in the executor never runs; the loop's thread, which imported the module, may call
# it directly, and asyncio.to_thread() and the default executor's threads may not. Each line is
# checked against the contract (tests/ffi/run.sh requires exit status 0) as well as compared with
# the source's run. Every wait is bounded (WAIT), and so is the whole client (pwdeadline).
import asyncio
import concurrent.futures as cf
import multiprocessing as mp
import pw
import pwdeadline

WAIT = 30  # (seconds: a handshake that fails ends the wait with an error)


def expect(label, got, want):
    print(label, got)
    if got != want:
        raise SystemExit(f"{label} {got!r}, expected {want!r}")


async def caught(aw):  # what awaiting aw raises, as type and args
    try:
        await asyncio.wait_for(aw, WAIT)
    except BaseException as e:  # (CancelledError too)
        return type(e).__name__, e.args
    return None


def _init(started, release, entered):  # (each worker, as it starts)
    global _started, _release, _entered
    _started, _release, _entered = started, release, entered


def _held(n):  # (in a worker) say it has started, wait for the release, then compute
    _started.release()
    if not _release.wait(WAIT):
        raise TimeoutError("never released")
    return pw.fib(n)


def _entering(n):  # (in a worker) say it has entered, then compute
    _entered.release()
    return pw.fib(n)


async def main():
    loop = asyncio.get_running_loop()
    refused = ("RuntimeError", ("fib() is compiled by Pystachy, whose runtime is single-threaded: call it from the thread that imported its module",))
    expect("loop thread:", pw.fib(10), 55)
    expect("to_thread:", await caught(asyncio.to_thread(pw.fib, 10)), refused)
    expect("default executor:", await caught(loop.run_in_executor(None, pw.fib, 10)), refused)
    expect("loop thread again:", pw.fib(20), 6765)

    ctx = mp.get_context("spawn")
    started, release, entered = ctx.Semaphore(0), ctx.Event(), ctx.Semaphore(0)

    async def has_started():  # a worker has started a _held call (a thread waits, not the loop)
        return await asyncio.to_thread(started.acquire, True, WAIT)

    async def wait(f):
        return await asyncio.wrap_future(f)

    async def dispatched(fs):  # the executor has marked each call running. It signals nothing
        # when it does, so this polls the futures' state, for WAIT at most
        end = loop.time() + WAIT
        while not all(f.running() for f in fs):
            if loop.time() > end:
                return False
            await asyncio.sleep(0.01)
        return True

    with cf.ProcessPoolExecutor(2, mp_context=ctx, initializer=_init, initargs=(started, release, entered)) as ex:
        # the loop runs while a worker holds a call that only the loop releases
        job = loop.run_in_executor(ex, _held, 30)
        expect("a worker holds the job:", await has_started(), True)
        expect("the job is pending while the loop runs:", job.done(), False)
        release.set()
        expect("its result:", await asyncio.wait_for(job, WAIT), 832040)
        jobs = asyncio.gather(*[loop.run_in_executor(ex, pw.fib, n) for n in (10, 20, 30)])
        expect("gather:", await asyncio.wait_for(jobs, WAIT), [55, 6765, 832040])
        expect("raises:", await caught(loop.run_in_executor(ex, pw.check, -1)), ("ValueError", ("negative: -1",)))

        # a timeout stops the waiting, not the call that a worker has started
        release.clear()
        f = ex.submit(_held, 40)
        expect("a worker holds the call:", await has_started(), True)
        expect("wait_for:", await caught(asyncio.wait_for(asyncio.wrap_future(f), 0.01)), ("TimeoutError", ()))
        expect("cancel() of the started call:", f.cancel(), False)
        release.set()
        expect("its result:", await asyncio.wait_for(asyncio.wrap_future(f), WAIT), 102334155)

        # cancellation: only a call still pending in the executor can be cancelled. Two held calls
        # keep both workers. The executor dispatches the next calls to its call queue, which holds
        # max_workers + EXTRA_QUEUED_CALLS of them, and marks them running, though no worker has
        # entered them: cancel() fails. The last call stays pending, since no worker can free a
        # slot in the queue before the release
        release.clear()
        held = [ex.submit(_held, 1) for _ in range(2)]
        for _ in held:
            expect("a worker holds a call:", await has_started(), True)
        queued = [ex.submit(_entering, 2) for _ in range(2 + cf.process.EXTRA_QUEUED_CALLS)]
        last = ex.submit(_entering, 3)
        expect("the queued calls dispatched:", await dispatched(queued), True)
        expect("a worker entered one:", entered.acquire(False), False)
        expect("cancel() of a dispatched call:", [f.cancel() for f in queued], [False] * len(queued))
        expect("the last call pending:", (last.running(), last.done()), (False, False))
        tasks = [asyncio.create_task(wait(held[0])), asyncio.create_task(wait(last))]
        await asyncio.sleep(0)  # (both tasks wait now)
        for t in tasks:
            t.cancel()
        expect("cancelled tasks:", [await caught(t) for t in tasks], [("CancelledError", ())] * 2)
        expect("the started call cancelled:", held[0].cancelled(), False)
        expect("the pending call cancelled:", last.cancelled(), True)
        release.set()
        expect("the held calls finish:", [await asyncio.wait_for(wait(f), WAIT) for f in held], [1, 1])
        expect("the dispatched calls run:", [await asyncio.wait_for(wait(f), WAIT) for f in queued], [1] * len(queued))
        expect("entered: each dispatched call, not the cancelled one:",
               [entered.acquire(True, WAIT) for _ in queued] + [entered.acquire(False)], [True] * len(queued) + [False])


if __name__ == "__main__":
    pwdeadline.start(90)
    asyncio.run(main())
