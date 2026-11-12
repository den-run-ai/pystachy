# Adapted from CPython 3.13.16 Lib/test/test_coroutines.py (SHA-256
# 161fbe91f6a7c92cdc887a4c824e6c76b33eb7bae449e58203c6ef98960279e5), commit
# cbc944f4bc59639a444dd971c737788ba2283a91: CoroutineTest's test_func_2, test_func_6,
# test_func_12, test_func_14, test_func_15, test_func_16, test_func_17, test_func_19,
# test_await_1, test_await_2, test_await_4, test_await_7, test_await_8, test_await_10,
# test_await_11 and test_await_15.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) and assertRaises print
# what they check, so the recording holds the values. run_async(coro) runs the coroutine as
# upstream's does, printing each value it yields; the value it returns, which upstream takes from
# StopIteration's args, is printed by result_of(), a coroutine that awaits it. test_func_12's g
# reads the coroutine it sends to from a module variable annotated Coroutine[None, None, None],
# and awaits nop() where upstream's awaits an undefined name that its ValueError keeps it from
# reaching. The classes test_await_7 and test_await_8 define are the module's (test_await_7's
# named Awaitable7), as Pystachy compiles no class inside a function.
# EXCLUDED upstream cases:
# - StopIteration's value and args (test_func_15's and test_func_17's 'spam'): a coroutine's
#   return value is what await gives (tests/deviations/gen_stop_value.py)
# - send() of a value other than None (test_func_13, test_await_14's send('spam')): a coroutine's
#   send type is None, a compile-time error (tests/errors/generators/coro_send_value.py)
# - __await__() of a coroutine and its coroutine_wrapper (run_async__await__, test_func_10,
#   test_func_11, test_func_18, test_coro_wrapper_*), cr_await, cr_frame, cr_code, co_flags,
#   inspect.getcoroutinestate and repr() of a coroutine: no frames or introspection
# - "coroutine ... was never awaited" warnings (test_func_9, OriginTrackingTest): a dropped
#   coroutine is not finalized (tests/deviations/gen_finalization.py)
# - yield from of a coroutine in a generator (test_func_7, test_func_8): rejected as the program
#   compiles; iterating a coroutine (test_func_4, test_func_5): rejected as the program compiles,
#   where CPython raises TypeError
# - __await__ that returns a non-iterator, a coroutine or an iterator object (test_await_5,
#   test_await_6, test_await_12, test_await_13, test_await_14's Wrapper): an __await__ is
#   supported where it is a generator method
# - test_await_3 (an __await__ that yields from a list), test_await_9 (await of calls of
#   lambdas and class attributes), test_await_16 (exception __context__)
# - async with, async for and asynchronous comprehensions (test_with_*, test_for_*, test_comp_*,
#   test_nested_comp): not supported; copy, pickle and the C API tests
import types
from collections.abc import Coroutine


async def result_of(coro):
    print("result", await coro)


def run_async(coro) -> None:
    c = result_of(coro)
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        pass


def test_func_2() -> None:
    async def foo():
        raise StopIteration

    try:
        run_async(foo())
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_func_6() -> None:
    @types.coroutine
    def bar():
        yield 1
        yield 2

    async def foo():
        await bar()

    f = foo()
    print("assertEqual", f.send(None), 1)
    print("assertEqual", f.send(None), 2)
    try:
        f.send(None)
    except StopIteration:
        print("assertRaises StopIteration")


@types.coroutine
def nop():
    yield


async def g():
    i = me.send(None)
    await nop()


me: Coroutine[None, None, None] = g()


def test_func_12() -> None:
    try:
        me.send(None)
    except ValueError as e:
        print("assertRaisesRegex ValueError", e)


def test_func_14() -> None:
    @types.coroutine
    def gen():
        yield

    async def coro():
        try:
            await gen()
        except GeneratorExit:
            await gen()

    c = coro()
    c.send(None)
    try:
        c.close()
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_func_15() -> None:
    async def spammer():
        return 'spam'

    async def reader(coro):
        return await coro

    spammer_coro = spammer()

    try:
        reader(spammer_coro).send(None)
    except StopIteration:
        print("assertRaises StopIteration")

    try:
        reader(spammer_coro).send(None)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_func_16() -> None:
    @types.coroutine
    def nop():
        yield

    async def send():
        await nop()
        return 'spam'

    async def read(coro):
        await nop()
        return await coro

    spammer = send()

    reader = read(spammer)
    reader.send(None)
    reader.send(None)
    try:
        reader.throw(Exception('ham'))
    except Exception as e:
        print("assertRaisesRegex Exception", e)

    reader = read(spammer)
    reader.send(None)
    try:
        reader.send(None)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)

    try:
        reader.throw(Exception('wat'))
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_func_17() -> None:
    async def coroutine():
        return 'spam'

    coro = coroutine()
    try:
        coro.send(None)
    except StopIteration:
        print("assertRaises StopIteration")

    try:
        coro.send(None)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)

    try:
        coro.throw(Exception('wat'))
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)

    # Closing a coroutine shouldn't raise any exception even if it's
    # already closed/exhausted (similar to generators)
    coro.close()
    coro.close()


CHK = 0


def test_func_19() -> None:
    @types.coroutine
    def foo():
        global CHK
        yield
        try:
            yield
        except GeneratorExit:
            CHK += 1

    async def coroutine():
        await foo()

    coro = coroutine()

    coro.send(None)
    coro.send(None)

    print("assertEqual", CHK, 0)
    coro.close()
    print("assertEqual", CHK, 1)

    for _ in range(3):
        # Closing a coroutine shouldn't raise any exception even if it's
        # already closed/exhausted (similar to generators)
        coro.close()
        print("assertEqual", CHK, 1)


def test_await_1() -> None:
    async def foo():
        await 1

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


def test_await_2() -> None:
    async def foo():
        await []

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


def test_await_4() -> None:
    async def bar():
        return 42

    async def foo():
        return await bar()

    run_async(foo())


class Awaitable7:
    def __await__(self):
        yield 42
        return 100


def test_await_7() -> None:
    async def foo():
        return (await Awaitable7())

    run_async(foo())


class Awaitable:
    pass


def test_await_8() -> None:
    async def foo(): return await Awaitable()

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


def test_await_10() -> None:
    async def baz():
        return 42

    async def bar():
        return baz()

    async def foo():
        return await (await bar())

    run_async(foo())


def test_await_11() -> None:
    def ident(val):
        return val

    async def bar():
        return 'spam'

    async def foo():
        return ident(val=await bar())

    async def foo2():
        return await bar(), 'ham'

    run_async(foo2())
    run_async(foo())


def test_await_15() -> None:
    @types.coroutine
    def nop():
        yield

    async def coroutine():
        await nop()

    async def waiter(coro):
        await coro

    coro = coroutine()
    coro.send(None)

    try:
        waiter(coro).send(None)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)
    coro.close()


test_func_2()
test_func_6()
test_func_12()
test_func_14()
test_func_15()
test_func_16()
test_func_17()
test_func_19()
test_await_1()
test_await_2()
test_await_4()
test_await_7()
test_await_8()
test_await_10()
test_await_11()
test_await_15()
