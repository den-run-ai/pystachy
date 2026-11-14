# Adapted from CPython 3.13.16 Lib/test/test_asyncio/test_futures.py (SHA-256
# fb015cd1e5f05287477da1a6d5a024987bd4cc7b60320bddd50f2a37da4008ae): BaseFutureTests'
# test_initial_state, test_constructor_use_running_loop, test_constructor_use_global_loop,
# test_future_cancel_message_getter, test_cancel, test_result, test_exception,
# and test_set_result_unless_cancelled, and BaseFutureDoneCallbackTests'
# test_callbacks_invoked_on_set_result and test_callbacks_invoked_on_set_exception, as
# PyFutureTests runs them (the pure-Python Future that lib/asyncio is).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name with a new event loop for setUp's
# test loop; assertEqual(a, b) and assertRaises print what they check, so the recording holds
# the values. A Future's result type is named where it is made (asyncio.Future[int]): its
# calls of set_result(None) and set_exception(None), which raise InvalidStateError before they
# look at their argument, pass a value of its type. run_briefly() is test_utils'.
# EXCLUDED upstream cases:
# - test_constructor_without_loop: get_event_loop() makes a loop where none is set
#   (lib/compatibility.md#asyncio); test_constructor_positional, test_uninitialized,
#   test_generic_alias, test_copy_state, test_wrap_future*: positional arguments, uninitialized
#   futures, GenericAlias and concurrent.futures are rejected as the program compiles
# - test_future_cancel_message_setter's del, test_stop_iteration_exception (exc.__cause__),
#   test_exception_class (a class given for an exception), test_future_stop_iteration_args
#   (StopIteration's args), test_future_iter_throw (throw()'s deprecated signature),
#   test_yield_from_twice (a future's __await__ yields None, not the future: lib/compatibility.md),
#   test_iter (yield from of a future: a Future has no __iter__, rejected as the program compiles)
# - test_future_repr (callbacks' reprs and reprlib), test_tb_logger_*, test_log_traceback,
#   test_future_source_traceback, test_future_exception_never_retrieved*, test_future_del_*,
#   refcycles: no logging, debug tracebacks or finalizers
# - remove_done_callback() (test_callbacks_remove_*, test_remove_done_callback*), the list and
#   evil __eq__ mutation tests, C-only tests, DuckFuture and inheritance tests
import asyncio
from asyncio import futures


def run_briefly(loop: asyncio.AbstractEventLoop) -> None:
    async def once() -> None:
        pass
    loop.run_until_complete(once())


def test_initial_state() -> None:
    loop = asyncio.new_event_loop()
    f: asyncio.Future[int] = asyncio.Future(loop=loop)
    print("assertFalse", f.cancelled())
    print("assertFalse", f.done())
    f.cancel()
    print("assertTrue", f.cancelled())
    loop.close()


def test_constructor_use_running_loop() -> None:
    loop = asyncio.new_event_loop()

    async def test() -> asyncio.Future[int]:
        f: asyncio.Future[int] = asyncio.Future()
        return f
    f = loop.run_until_complete(test())
    print("assertIs", f._loop is loop)
    print("assertIs", f.get_loop() is loop)
    loop.close()


def test_constructor_use_global_loop() -> None:
    # Deprecated in 3.10, undeprecated in 3.12
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    f: asyncio.Future[int] = asyncio.Future()
    print("assertIs", f._loop is loop)
    print("assertIs", f.get_loop() is loop)
    asyncio.set_event_loop(None)
    loop.close()


def test_future_cancel_message_getter() -> None:
    loop = asyncio.new_event_loop()
    f: asyncio.Future[int] = asyncio.Future(loop=loop)
    print("assertTrue", hasattr(f, '_cancel_message'))
    print("assertEqual", f._cancel_message, None)

    f.cancel('my message')
    try:
        loop.run_until_complete(f)
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")
    print("assertEqual", f._cancel_message, 'my message')
    loop.close()


def test_cancel() -> None:
    loop = asyncio.new_event_loop()
    f: asyncio.Future[int] = asyncio.Future(loop=loop)
    print("assertTrue", f.cancel())
    print("assertTrue", f.cancelled())
    print("assertTrue", f.done())
    try:
        f.result()
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")
    try:
        f.exception()
    except asyncio.CancelledError:
        print("assertRaises asyncio.CancelledError")
    try:
        f.set_result(0)
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")
    try:
        f.set_exception(RuntimeError())
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")
    print("assertFalse", f.cancel())
    loop.close()


def test_result() -> None:
    loop = asyncio.new_event_loop()
    f: asyncio.Future[int] = asyncio.Future(loop=loop)
    try:
        f.result()
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")

    f.set_result(42)
    print("assertFalse", f.cancelled())
    print("assertTrue", f.done())
    print("assertEqual", f.result(), 42)
    print("assertEqual", f.exception(), None)
    try:
        f.set_result(0)
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")
    try:
        f.set_exception(RuntimeError())
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")
    print("assertFalse", f.cancel())
    loop.close()


def test_exception() -> None:
    exc = RuntimeError()
    loop = asyncio.new_event_loop()
    f: asyncio.Future[int] = asyncio.Future(loop=loop)
    try:
        f.exception()
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")

    f.set_exception(exc)
    print("assertFalse", f.cancelled())
    print("assertTrue", f.done())
    try:
        f.result()
    except RuntimeError:
        print("assertRaises RuntimeError")
    print("assertEqual", repr(f.exception()), repr(exc))
    try:
        f.set_result(0)
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")
    try:
        f.set_exception(RuntimeError())
    except asyncio.InvalidStateError:
        print("assertRaises asyncio.InvalidStateError")
    print("assertFalse", f.cancel())
    loop.close()


def test_set_result_unless_cancelled() -> None:
    loop = asyncio.new_event_loop()
    fut: asyncio.Future[int] = asyncio.Future(loop=loop)
    fut.cancel()
    futures._set_result_unless_cancelled(fut, 2)
    print("assertTrue", fut.cancelled())
    loop.close()


def make_callback(bag: list[int], thing: int):
    # Create a callback function that appends thing to bag.
    def bag_appender(future: asyncio.Future[str]) -> None:
        bag.append(thing)
    return bag_appender


def test_callbacks_invoked_on_set_result() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bag: list[int] = []
    f: asyncio.Future[str] = asyncio.Future(loop=loop)
    f.add_done_callback(make_callback(bag, 42))
    f.add_done_callback(make_callback(bag, 17))

    print("assertEqual", bag, bag == [])
    f.set_result('foo')

    run_briefly(loop)

    print("assertEqual", bag, [42, 17])
    print("assertEqual", f.result(), 'foo')
    asyncio.set_event_loop(None)
    loop.close()


def test_callbacks_invoked_on_set_exception() -> None:
    loop = asyncio.new_event_loop()
    bag: list[int] = []
    f: asyncio.Future[str] = asyncio.Future(loop=loop)
    f.add_done_callback(make_callback(bag, 100))

    print("assertEqual", bag, bag == [])
    exc = RuntimeError()
    f.set_exception(exc)

    run_briefly(loop)

    print("assertEqual", bag, [100])
    print("assertEqual", repr(f.exception()), repr(exc))
    loop.close()


test_initial_state()
test_constructor_use_running_loop()
test_constructor_use_global_loop()
test_future_cancel_message_getter()
test_cancel()
test_result()
test_exception()
test_set_result_unless_cancelled()
test_callbacks_invoked_on_set_result()
test_callbacks_invoked_on_set_exception()
