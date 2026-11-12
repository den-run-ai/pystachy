# asyncio's synchronization and cancellation: a TaskGroup waits for its tasks; cancel() throws
# CancelledError into a task where it awaits; wait_for() and timeout() turn a cancellation
# into TimeoutError; a task's exception is raised where it is awaited; Lock, Event and Queue
# order their waiters as CPython's do (lib/compatibility.md#asyncio).
import asyncio


async def work(name: str, delay: float, out: list[str]) -> str:
    await asyncio.sleep(delay)
    out.append(name)
    return name.upper()


async def fail_after(delay: float) -> int:
    await asyncio.sleep(delay)
    raise ValueError("boom")


async def forever() -> None:
    while True:
        await asyncio.sleep(0.01)


async def main() -> None:
    out: list[str] = []
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(work("a", 0.02, out))
        t2 = tg.create_task(work("b", 0.01, out))
    print("taskgroup", out, t1.result(), t2.result())

    t = asyncio.create_task(forever())
    await asyncio.sleep(0.02)
    print("cancel", t.cancel())
    try:
        await t
    except asyncio.CancelledError:
        print("cancelled", t.cancelled(), t.done())

    try:
        await asyncio.wait_for(forever(), 0.02)
    except TimeoutError:
        print("wait_for timed out")

    try:
        async with asyncio.timeout(0.01):
            await asyncio.sleep(1)
    except TimeoutError:
        print("timeout")

    f = asyncio.create_task(fail_after(0.0))
    try:
        await f
    except ValueError as e:
        print("failed", e, f.done(), repr(f.exception()))

    lock = asyncio.Lock()
    order: list[int] = []

    async def locked(n: int) -> None:
        async with lock:
            order.append(n)
            await asyncio.sleep(0.001)
            order.append(-n)

    await asyncio.gather(locked(1), locked(2), locked(3))
    print("lock", order, lock.locked())

    ev = asyncio.Event()

    async def waiter() -> str:
        await ev.wait()
        return "woke"

    w = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    print("event", ev.is_set(), w.done())
    ev.set()
    print("waiter", await w)

    q: asyncio.Queue[int] = asyncio.Queue()

    async def producer() -> None:
        for i in range(3):
            await q.put(i)
        await q.put(-1)

    async def consumer() -> list[int]:
        got: list[int] = []
        v = await q.get()
        while v >= 0:
            got.append(v)
            v = await q.get()
        return got

    p = asyncio.create_task(producer())
    print("queue", await consumer(), q.empty())
    await p

    loop = asyncio.get_running_loop()
    seen: list[str] = []
    loop.call_later(0.002, seen.append, "later")
    loop.call_soon(seen.append, "soon")
    await asyncio.sleep(0.01)
    print("callbacks", seen)


asyncio.run(main())
