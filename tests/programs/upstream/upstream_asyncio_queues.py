# Adapted from CPython 3.13.16 Lib/test/test_asyncio/test_queues.py (SHA-256
# 8997747f29c7e39f5c42cfb21258c08ad7d5fcf965b799af151491cc0aaab984): QueueBasicTests'
# test_empty, test_full, test_order and test_maxsize, QueueGetTests' test_blocking_get,
# test_blocking_get_wait, test_nonblocking_get and test_nonblocking_get_exception,
# QueuePutTests' test_blocking_put, test_blocking_put_wait, test_nonblocking_put and
# test_nonblocking_put_exception, and _QueueJoinTestMixin's test_task_done_underflow and
# test_task_done, as QueueJoinTests runs them.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a coroutine of the same name, which asyncio.run() runs as the
# IsolatedAsyncioTestCase would (also the synchronous ones, whose queues need a running loop
# only where they wait); assertEqual(a, b) and assertRaises print what they check, so the
# recording holds the values. A queue's item type is named where it is made
# (asyncio.Queue[int]); the flags and the sum that the coroutines change are lists, where
# upstream's are nonlocal variables, and test_order's items are gathered by a loop.
# EXCLUDED upstream cases:
# - test_repr, test_str (an object's address, and the default repr), test_generic_alias,
#   test_float_maxsize (an int maxsize), LifoQueue, PriorityQueue, shutdown()
#   (QueueShutdownTests, which use exception groups) and the tests that replace a queue's
#   getters or putters with the loop's futures or race cancellations against them
import asyncio


async def test_empty() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    print("assertTrue", q.empty())
    await q.put(1)
    print("assertFalse", q.empty())
    print("assertEqual", 1, await q.get())
    print("assertTrue", q.empty())


async def test_full() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    print("assertFalse", q.full())

    q = asyncio.Queue(maxsize=1)
    await q.put(1)
    print("assertTrue", q.full())


async def test_order() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    for i in [1, 3, 2]:
        await q.put(i)

    items: list[int] = []
    for _ in range(3):
        items.append(await q.get())
    print("assertEqual", [1, 3, 2], items)


have_been_put: list[int] = []


async def putter(q: asyncio.Queue[int]) -> bool:
    for i in range(3):
        await q.put(i)
        have_been_put.append(i)
    return True


async def test_maxsize() -> None:
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=2)
    print("assertEqual", 2, q.maxsize)

    t = asyncio.create_task(putter(q))
    for i in range(2):
        await asyncio.sleep(0)

    # The putter is blocked after putting two items.
    print("assertEqual", [0, 1], have_been_put)
    print("assertEqual", 0, await q.get())

    # Let the putter resume and put last item.
    await asyncio.sleep(0)
    print("assertEqual", [0, 1, 2], have_been_put)
    print("assertEqual", 1, await q.get())
    print("assertEqual", 2, await q.get())

    print("assertTrue", t.done())
    print("assertTrue", t.result())


async def test_blocking_get() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    q.put_nowait(1)

    print("assertEqual", 1, await q.get())


finished = [False]


async def queue_get(q: asyncio.Queue[int], started: asyncio.Event) -> int:
    started.set()
    res = await q.get()
    finished[0] = True
    return res


async def test_blocking_get_wait() -> None:
    loop = asyncio.get_running_loop()
    q: asyncio.Queue[int] = asyncio.Queue()
    started = asyncio.Event()
    finished[0] = False

    queue_get_task = asyncio.create_task(queue_get(q, started))
    await started.wait()
    print("assertFalse", finished[0])
    loop.call_later(0.01, q.put_nowait, 1)
    res = await queue_get_task
    print("assertTrue", finished[0])
    print("assertEqual", 1, res)


async def test_nonblocking_get() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    q.put_nowait(1)
    print("assertEqual", 1, q.get_nowait())


async def test_nonblocking_get_exception() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    try:
        q.get_nowait()
    except asyncio.QueueEmpty:
        print("assertRaises asyncio.QueueEmpty")


async def test_blocking_put() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()

    # No maxsize, won't block.
    await q.put(1)
    print("assertEqual", 1, await q.get())


async def queue_put(q: asyncio.Queue[int], started: asyncio.Event) -> None:
    started.set()
    await q.put(1)
    await q.put(2)
    finished[0] = True


async def test_blocking_put_wait() -> None:
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    started = asyncio.Event()
    finished[0] = False

    loop = asyncio.get_running_loop()
    loop.call_later(0.01, q.get_nowait)
    queue_put_task = asyncio.create_task(queue_put(q, started))
    await started.wait()
    print("assertFalse", finished[0])
    await queue_put_task
    print("assertTrue", finished[0])


async def test_nonblocking_put() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    q.put_nowait(1)
    print("assertEqual", 1, q.get_nowait())


async def test_nonblocking_put_exception() -> None:
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=1, )
    q.put_nowait(1)
    try:
        q.put_nowait(2)
    except asyncio.QueueFull:
        print("assertRaises asyncio.QueueFull")


async def test_task_done_underflow() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    try:
        q.task_done()
    except ValueError:
        print("assertRaises ValueError")


accumulator = [0]
running = [True]


async def worker(q: asyncio.Queue[int]) -> None:
    while running[0]:
        item = await q.get()
        accumulator[0] += item
        q.task_done()


async def test_task_done() -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    for i in range(100):
        q.put_nowait(i)

    # Two workers get items from the queue and call task_done after each.
    # Join the queue and assert all items have been processed.
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(worker(q))
                 for index in range(2)]

        await q.join()
        print("assertEqual", sum(range(100)), accumulator[0])

        # close running generators
        running[0] = False
        for i in range(len(tasks)):
            q.put_nowait(0)


asyncio.run(test_empty())
asyncio.run(test_full())
asyncio.run(test_order())
asyncio.run(test_maxsize())
asyncio.run(test_blocking_get())
asyncio.run(test_blocking_get_wait())
asyncio.run(test_nonblocking_get())
asyncio.run(test_nonblocking_get_exception())
asyncio.run(test_blocking_put())
asyncio.run(test_blocking_put_wait())
asyncio.run(test_nonblocking_put())
asyncio.run(test_nonblocking_put_exception())
asyncio.run(test_task_done_underflow())
asyncio.run(test_task_done())
