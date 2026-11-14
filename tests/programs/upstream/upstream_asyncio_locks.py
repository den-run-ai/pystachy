# Adapted from CPython 3.13.16 Lib/test/test_asyncio/test_locks.py (SHA-256
# 5152e87ccfc64631ed071e76adaa43c0b5bebed19bf708f7c725476541ee2c06): LockTests'
# test_acquire, test_acquire_cancel, test_release_not_acquired, test_release_no_waiters and
# test_context_manager, and EventTests' test_wait, test_wait_on_set, test_wait_cancel,
# test_clear and test_clear_with_waiters.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each async test method becomes a coroutine of the same name, which asyncio.run() runs as the
# IsolatedAsyncioTestCase would; assertEqual(a, b) and assertRaises print what they check, so
# the recording holds the values. Results are lists of ints, which the coroutines of a test
# append to, and the waiting coroutines are module functions taking the lock or event.
# EXCLUDED upstream cases:
# - test_lock: await of a Lock, which has no __await__, is a TypeError in CPython and rejected
#   as the program compiles here
# - test_repr (an object's default repr, with its address), test_lock_doesnt_accept_loop_parameter
#   (the loop argument is rejected as the program compiles), test_cancel_race,
#   test_cancel_release_race and test_finished_waiter_cancelled (they replace the loop's
#   create_future): not in lib/asyncio's Lock
# - Condition, Semaphore, BoundedSemaphore and Barrier: not in lib/asyncio
import asyncio


async def acquirer(lock: asyncio.Lock, result: list[int], n: int) -> bool:
    if await lock.acquire():
        result.append(n)
    return True


async def test_acquire() -> None:
    lock = asyncio.Lock()
    result: list[int] = []

    print("assertTrue", await lock.acquire())

    t1 = asyncio.create_task(acquirer(lock, result, 1))
    t2 = asyncio.create_task(acquirer(lock, result, 2))

    await asyncio.sleep(0)
    print("assertEqual", result)

    lock.release()
    await asyncio.sleep(0)
    print("assertEqual", result, [1])

    await asyncio.sleep(0)
    print("assertEqual", result, [1])

    t3 = asyncio.create_task(acquirer(lock, result, 3))

    lock.release()
    await asyncio.sleep(0)
    print("assertEqual", result, [1, 2])

    lock.release()
    await asyncio.sleep(0)
    print("assertEqual", result, [1, 2, 3])

    print("assertTrue", t1.done())
    print("assertTrue", t1.result())
    print("assertTrue", t2.done())
    print("assertTrue", t2.result())
    print("assertTrue", t3.done())
    print("assertTrue", t3.result())


async def test_acquire_cancel() -> None:
    lock = asyncio.Lock()
    print("assertTrue", await lock.acquire())

    task = asyncio.create_task(lock.acquire())
    asyncio.get_running_loop().call_soon(task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")
    print("assertFalse", bool(lock._waiters))


async def test_release_not_acquired() -> None:
    lock = asyncio.Lock()

    try:
        lock.release()
    except RuntimeError:
        print("assertRaises RuntimeError")


async def test_release_no_waiters() -> None:
    lock = asyncio.Lock()
    await lock.acquire()
    print("assertTrue", lock.locked())

    lock.release()
    print("assertFalse", lock.locked())


async def test_context_manager() -> None:
    lock = asyncio.Lock()
    print("assertFalse", lock.locked())

    async with lock:
        print("assertTrue", lock.locked())

    print("assertFalse", lock.locked())


async def waiter(ev: asyncio.Event, result: list[int], n: int) -> None:
    if await ev.wait():
        result.append(n)


async def test_wait() -> None:
    ev = asyncio.Event()
    print("assertFalse", ev.is_set())

    result: list[int] = []

    t1 = asyncio.create_task(waiter(ev, result, 1))
    t2 = asyncio.create_task(waiter(ev, result, 2))

    await asyncio.sleep(0)
    print("assertEqual", result)

    t3 = asyncio.create_task(waiter(ev, result, 3))

    ev.set()
    await asyncio.sleep(0)
    print("assertEqual", result, [3, 1, 2])

    print("assertTrue", t1.done())
    print("assertIsNone", t1.result())
    print("assertTrue", t2.done())
    print("assertIsNone", t2.result())
    print("assertTrue", t3.done())
    print("assertIsNone", t3.result())


async def test_wait_on_set() -> None:
    ev = asyncio.Event()
    ev.set()

    res = await ev.wait()
    print("assertTrue", res)


async def test_wait_cancel() -> None:
    ev = asyncio.Event()

    wait = asyncio.create_task(ev.wait())
    asyncio.get_running_loop().call_soon(wait.cancel)
    try:
        await wait
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")
    print("assertFalse", bool(ev._waiters))


async def test_clear() -> None:
    ev = asyncio.Event()
    print("assertFalse", ev.is_set())

    ev.set()
    print("assertTrue", ev.is_set())

    ev.clear()
    print("assertFalse", ev.is_set())


async def setter(ev: asyncio.Event, result: list[int]) -> bool:
    if await ev.wait():
        result.append(1)
    return True


async def test_clear_with_waiters() -> None:
    ev = asyncio.Event()
    result: list[int] = []

    t = asyncio.create_task(setter(ev, result))
    await asyncio.sleep(0)
    print("assertEqual", result)

    ev.set()
    ev.clear()
    print("assertFalse", ev.is_set())

    ev.set()
    ev.set()
    print("assertEqual", 1, len(ev._waiters))

    await asyncio.sleep(0)
    print("assertEqual", result, [1])
    print("assertEqual", 0, len(ev._waiters))

    print("assertTrue", t.done())
    print("assertTrue", t.result())


asyncio.run(test_acquire())
asyncio.run(test_acquire_cancel())
asyncio.run(test_release_not_acquired())
asyncio.run(test_release_no_waiters())
asyncio.run(test_context_manager())
asyncio.run(test_wait())
asyncio.run(test_wait_on_set())
asyncio.run(test_wait_cancel())
asyncio.run(test_clear())
asyncio.run(test_clear_with_waiters())
