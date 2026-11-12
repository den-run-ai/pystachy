# Adapted from CPython 3.13.16 Lib/test/test_asyncio/test_tasks.py (SHA-256
# 0c37b543c8f0cc0cc6557964e3e45694788ddd0cbb549f0e635c90d91812d364): BaseTaskTests'
# test_task_cancel_message_getter, test_task_awaits_on_itself, test_ensure_future_coroutine,
# test_task_basics, test_cancelling, test_uncancel_basic, test_cancel_task_catching,
# test_cancel_task_ignoring, test_cancel_current_task, test_sleep_when_delay_is_nan and
# test_task_set_methods, as PyTask_PyFuture_Tests runs them (lib/asyncio's Task and Future are
# the pure-Python ones).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name with a new event loop for setUp's test
# loop, new_task() and new_future() make a Task and a Future[None]; assertEqual(a, b) and
# assertRaises print what they check, so the recording holds the values. run_briefly() is
# test_utils'. A coroutine that awaits or cancels the task that runs it reads the task from a
# module variable, where upstream's reads a local of the test that closes over it. A repr is
# checked for its state only (" cancelling "), as upstream's tests check it. test_task_basics
# defines its inner coroutines before outer(), which reads them as it is defined in Pystachy.
# EXCLUDED upstream cases:
# - cm.exception.args (test_task_cancel_message_getter's last check) and the CancelledError's
#   message and context (test_cancel_with_message_*, test_cancellation_exception_context): no
#   exception attributes; asyncio.ensure_future() without a loop where none is set makes one
#   (lib/compatibility.md#asyncio), not RuntimeError
# - wait(), as_completed(), shield(), run_coroutine_threadsafe(), custom task factories and
#   awaitables other than coroutines and futures: not in lib/asyncio
# - the TestLoop's virtual time (test_cancel, test_wait*, test_sleep, test_task_cancel_sleeping_task,
#   ...), repr() of coroutines, get_stack(), print_stack(), contextvars, exception groups, log
#   capture, the C Task and Future, refcycles and mock patching
import asyncio
from asyncio import futures


def run_briefly(loop: asyncio.AbstractEventLoop) -> None:
    async def once() -> None:
        pass
    loop.run_until_complete(once())


def new_future(loop: asyncio.AbstractEventLoop) -> asyncio.Future[None]:
    f: asyncio.Future[None] = asyncio.Future(loop=loop)
    return f


def test_task_cancel_message_getter() -> None:
    loop = asyncio.new_event_loop()

    async def coro() -> None:
        pass
    t = asyncio.Task(coro(), loop=loop)
    print("assertTrue", hasattr(t, '_cancel_message'))
    print("assertEqual", t._cancel_message, None)

    t.cancel('my message')
    print("assertEqual", t._cancel_message, 'my message')

    try:
        loop.run_until_complete(t)
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")
    loop.close()


async def awaits_itself() -> None:
    await self_task[0]


self_task: list[asyncio.Task[None]] = []


def test_task_awaits_on_itself() -> None:
    loop = asyncio.new_event_loop()
    task = asyncio.ensure_future(awaits_itself(), loop=loop)
    self_task.append(task)

    try:
        loop.run_until_complete(task)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", str(e).startswith('Task cannot await on itself'))
    loop.close()


def test_ensure_future_coroutine() -> None:
    loop = asyncio.new_event_loop()

    async def notmuch() -> str:
        return 'ok'
    t = asyncio.ensure_future(notmuch(), loop=loop)
    print("assertIs", t._loop is loop)
    loop.run_until_complete(t)
    print("assertTrue", t.done())
    print("assertEqual", t.result(), 'ok')

    async def test() -> asyncio.Task[str]:
        return asyncio.ensure_future(notmuch())
    t = loop.run_until_complete(test())
    print("assertIs", t._loop is loop)
    loop.run_until_complete(t)
    print("assertTrue", t.done())
    print("assertEqual", t.result(), 'ok')

    # Deprecated in 3.10, undeprecated in 3.12
    asyncio.set_event_loop(loop)
    t = asyncio.ensure_future(notmuch())
    print("assertIs", t._loop is loop)
    loop.run_until_complete(t)
    print("assertTrue", t.done())
    print("assertEqual", t.result(), 'ok')
    asyncio.set_event_loop(None)
    loop.close()


def test_task_basics() -> None:
    loop = asyncio.new_event_loop()

    # (inner1 and inner2 are defined before outer, which reads them)
    async def inner1() -> int:
        return 42

    async def inner2() -> int:
        return 1000

    async def outer() -> int:
        a = await inner1()
        b = await inner2()
        return a+b

    t = outer()
    print("assertEqual", loop.run_until_complete(t), 1042)
    loop.close()


def test_cancelling() -> None:
    loop = asyncio.new_event_loop()

    async def task() -> None:
        await asyncio.sleep(10)

    try:
        t = asyncio.Task(task(), loop=loop)
        print("assertFalse", t.cancelling())
        print("assertNotIn", " cancelling " in repr(t))
        print("assertTrue", t.cancel())
        print("assertTrue", t.cancelling())
        print("assertIn", " cancelling " in repr(t))

        # Since we commented out two lines from Task.cancel(),
        # this t.cancel() call now returns True.
        # self.assertFalse(t.cancel())
        print("assertTrue", t.cancel())

        try:
            loop.run_until_complete(t)
        except asyncio.CancelledError:
            print("assertRaises asyncio.CancelledError")
    finally:
        loop.close()


async def uncancelling() -> None:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        current = asyncio.current_task()
        assert current is not None
        current.uncancel()
        await asyncio.sleep(10)


def test_uncancel_basic() -> None:
    loop = asyncio.new_event_loop()

    try:
        t = asyncio.Task(uncancelling(), loop=loop)
        loop.run_until_complete(asyncio.sleep(0.01))

        # Cancel first sleep
        print("assertTrue", t.cancel())
        print("assertIn", " cancelling " in repr(t))
        print("assertEqual", t.cancelling(), 1)
        print("assertFalse", t.cancelled())  # Task is still not complete
        loop.run_until_complete(asyncio.sleep(0.01))

        # after .uncancel()
        print("assertNotIn", " cancelling " in repr(t))
        print("assertEqual", t.cancelling(), 0)
        print("assertFalse", t.cancelled())  # Task is still not complete

        # Cancel second sleep
        print("assertTrue", t.cancel())
        print("assertEqual", t.cancelling(), 1)
        print("assertFalse", t.cancelled())  # Task is still not complete
        try:
            loop.run_until_complete(t)
        except asyncio.CancelledError:
            print("assertRaises asyncio.CancelledError")
        print("assertTrue", t.cancelled())  # Finally, task complete
        print("assertTrue", t.done())

        # uncancel is no longer effective after the task is complete
        t.uncancel()
        print("assertTrue", t.cancelled())
        print("assertTrue", t.done())
    finally:
        loop.close()


def test_cancel_task_catching() -> None:
    loop = asyncio.new_event_loop()
    fut1 = new_future(loop)
    fut2 = new_future(loop)

    async def task() -> int:
        await fut1
        try:
            await fut2
        except asyncio.CancelledError:
            return 42
        return 0

    t = asyncio.Task(task(), loop=loop)
    run_briefly(loop)
    print("assertIs", t._fut_waiter is fut1)  # White-box test.
    fut1.set_result(None)
    run_briefly(loop)
    print("assertIs", t._fut_waiter is fut2)  # White-box test.
    t.cancel()
    print("assertTrue", fut2.cancelled())
    res = loop.run_until_complete(t)
    print("assertEqual", res, 42)
    print("assertFalse", t.cancelled())
    loop.close()


def test_cancel_task_ignoring() -> None:
    loop = asyncio.new_event_loop()
    fut1 = new_future(loop)
    fut2 = new_future(loop)
    fut3: asyncio.Future[int] = asyncio.Future(loop=loop)

    async def task() -> int:
        await fut1
        try:
            await fut2
        except asyncio.CancelledError:
            pass
        res = await fut3
        return res

    t = asyncio.Task(task(), loop=loop)
    run_briefly(loop)
    print("assertIs", t._fut_waiter is fut1)  # White-box test.
    fut1.set_result(None)
    run_briefly(loop)
    print("assertIs", t._fut_waiter is fut2)  # White-box test.
    t.cancel()
    print("assertTrue", fut2.cancelled())
    run_briefly(loop)
    print("assertIs", t._fut_waiter is fut3)  # White-box test.
    fut3.set_result(42)
    res = loop.run_until_complete(t)
    print("assertEqual", res, 42)
    print("assertFalse", fut3.cancelled())
    print("assertFalse", t.cancelled())
    loop.close()


cancelled_task: list[asyncio.Task[int]] = []


async def cancels_itself() -> int:
    t = cancelled_task[0]
    t.cancel()
    print("assertTrue", t._must_cancel)  # White-box test.
    # The sleep should be cancelled immediately.
    await asyncio.sleep(100)
    return 12


def test_cancel_current_task() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    t = asyncio.Task(cancels_itself(), loop=loop)
    cancelled_task.append(t)
    print("assertFalse", t.cancelled())
    try:
        loop.run_until_complete(t)
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")
    print("assertTrue", t.done())
    print("assertTrue", t.cancelled())
    print("assertFalse", t._must_cancel)  # White-box test.
    print("assertFalse", t.cancel())
    asyncio.set_event_loop(None)
    loop.close()


def test_sleep_when_delay_is_nan() -> None:
    loop = asyncio.new_event_loop()

    async def sleeper() -> None:
        await asyncio.sleep(float("nan"))

    t = asyncio.Task(sleeper(), loop=loop)

    try:
        loop.run_until_complete(t)
    except ValueError:
        print("assertRaises ValueError")
    loop.close()


def test_task_set_methods() -> None:
    loop = asyncio.new_event_loop()

    async def notmuch() -> str:
        return 'ko'

    gen = notmuch()
    task = asyncio.Task(gen, loop=loop)

    try:
        task.set_result('ok')
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)

    try:
        task.set_exception(ValueError())
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)

    print("assertEqual", loop.run_until_complete(task), 'ko')
    loop.close()


test_task_cancel_message_getter()
test_task_awaits_on_itself()
test_ensure_future_coroutine()
test_task_basics()
test_cancelling()
test_uncancel_basic()
test_cancel_task_catching()
test_cancel_task_ignoring()
test_cancel_current_task()
test_sleep_when_delay_is_nan()
test_task_set_methods()
