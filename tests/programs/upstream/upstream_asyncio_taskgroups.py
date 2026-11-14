# Adapted from CPython 3.13.16 Lib/test/test_asyncio/test_taskgroups.py (SHA-256
# 13db8bb96d28775cd313bacdafb7aba58da79eea09beedd001a764dd19877e7d): TestTaskGroup's
# test_taskgroup_01, test_taskgroup_02, test_taskgroup_03, test_cancellation,
# test_taskgroup_already_entered, test_taskgroup_double_enter and test_taskgroup_not_entered.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each async test method becomes a coroutine of the same name, which asyncio.run() runs as the
# IsolatedAsyncioTestCase would; assertEqual(a, b) and assertRaises print what they check, so
# the recording holds the values. The sleeps are a tenth of upstream's, in the same order.
# test_cancellation's counter is a list, which its coroutine changes, where upstream's is a
# nonlocal int.
# EXCLUDED upstream cases:
# - every case where a task of the group fails (test_taskgroup_04 onwards, the ExceptionGroup and
#   except* checks): exception groups are not supported, and a TaskGroup raises its first
#   failure's exception instead (lib/compatibility.md#asyncio)
# - test_taskgroup_finished (warnings.catch_warnings), test_taskgroup_task_context
#   (contextvars), the refcycle tests (gc), test_taskgroup_without_parent_task (a loop's
#   run_until_complete() of a coroutine that is not run by a task) and test_coro_closed_when_tg_closed
import asyncio
from asyncio import taskgroups


async def test_taskgroup_01() -> None:

    async def foo1() -> int:
        await asyncio.sleep(0.01)
        return 42

    async def foo2() -> int:
        await asyncio.sleep(0.02)
        return 11

    async with taskgroups.TaskGroup() as g:
        t1 = g.create_task(foo1())
        t2 = g.create_task(foo2())

    print("assertEqual", t1.result(), 42)
    print("assertEqual", t2.result(), 11)


async def test_taskgroup_02() -> None:

    async def foo1() -> int:
        await asyncio.sleep(0.01)
        return 42

    async def foo2() -> int:
        await asyncio.sleep(0.02)
        return 11

    async with taskgroups.TaskGroup() as g:
        t1 = g.create_task(foo1())
        await asyncio.sleep(0.015)
        t2 = g.create_task(foo2())

    print("assertEqual", t1.result(), 42)
    print("assertEqual", t2.result(), 11)


async def test_taskgroup_03() -> None:

    async def foo1() -> int:
        await asyncio.sleep(0.1)
        return 42

    async def foo2() -> int:
        await asyncio.sleep(0.02)
        return 11

    async with taskgroups.TaskGroup() as g:
        t1 = g.create_task(foo1())
        await asyncio.sleep(0.015)
        # cancel t1 explicitly, i.e. everything should continue
        # working as expected.
        t1.cancel()

        t2 = g.create_task(foo2())

    print("assertTrue", t1.cancelled())
    print("assertEqual", t2.result(), 11)


NUM = [0]


async def foo() -> None:
    try:
        await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        NUM[0] += 1
        raise


async def runner() -> None:
    async with taskgroups.TaskGroup() as g:
        for _ in range(5):
            g.create_task(foo())


async def test_cancellation() -> None:
    r = asyncio.create_task(runner())
    await asyncio.sleep(0.01)

    print("assertFalse", r.done())
    r.cancel()
    try:
        await r
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")

    print("assertEqual", NUM[0], 5)


async def test_taskgroup_already_entered() -> None:
    tg = taskgroups.TaskGroup()
    async with tg:
        try:
            async with tg:
                pass
        except RuntimeError as e:
            print("assertRaisesRegex RuntimeError", "has already been entered" in str(e))


async def test_taskgroup_double_enter() -> None:
    tg = taskgroups.TaskGroup()
    async with tg:
        pass
    try:
        async with tg:
            pass
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", "has already been entered" in str(e))


async def test_taskgroup_not_entered() -> None:
    tg = taskgroups.TaskGroup()
    coro = asyncio.sleep(0)
    try:
        tg.create_task(coro)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", "has not been entered" in str(e))


asyncio.run(test_taskgroup_01())
asyncio.run(test_taskgroup_02())
asyncio.run(test_taskgroup_03())
asyncio.run(test_cancellation())
asyncio.run(test_taskgroup_already_entered())
asyncio.run(test_taskgroup_double_enter())
asyncio.run(test_taskgroup_not_entered())
