# Adapted from CPython 3.13.16 Lib/test/test_asyncgen.py (SHA-256
# e32fc8d4dacbb0cd18926c032c59c1977a1120b8bd4b9b9f240a6500bbcde7ea): AsyncGenTest's
# test_async_gen_iteration_01, test_async_gen_iteration_02, test_async_gen_exception_03 to
# test_async_gen_exception_12, test_async_gen_asend_close_runtime_error and
# test_async_gen_athrow_close_runtime_error, and AsyncGenAsyncioTest's test_async_gen_expression_01,
# test_async_gen_expression_02, test_async_gen_await_same_anext_coro_twice and
# test_async_gen_await_same_aclose_coro_twice, whose event loop a driver that sends None replaces
# (asyncio.sleep() a @types.coroutine generator that yields once).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# AsyncGenSyntaxTest's cases are tests/errors/syntax/syntax_asyncgen_*.py.
# Each test method becomes a function of the same name; assertEqual and assertRaises print what
# they check, so the recording holds the values. An awaitable's __next__() is its send(None). The
# value that upstream reads from StopIteration's args (to_list()'s result, an item of an
# __anext__() awaitable) is what await gives: to_list() collects the items in a list it returns,
# drive() awaits an awaitable in a coroutine that prints each value it yields and the result, and
# compare_generators()'s async_iterate() awaits each __anext__() in a coroutine. Its items are
# kept as strings (str(), and type(ex).__name__ for an exception), as a list holds one type.
# Classes and the async generator that test_async_gen_exception_12 iterates are the module's, as
# Pystachy compiles no class inside a function and no closure over a variable assigned after it.
# EXCLUDED upstream cases:
# - test_async_gen_exception_10's send(100) of an __anext__() awaitable: a coroutine is sent None
#   as the program compiles (tests/errors/generators/coro_send_value.py); asend(100) of an async
#   generator annotated AsyncGenerator[int, int | None] raises the TypeError instead
# - test_async_gen_exception_12's RuntimeWarning: an awaitable never awaited prints none
#   (tests/deviations/agen_finalization.py)
# - throw() of an asend() or athrow() awaitable that has not started
#   (test_async_gen_asend_throw_concurrent_with_send and the three other *_concurrent_* cases):
#   Pystachy raises the exception at once, where CPython first checks that the async generator is
#   not running and then throws it into the async generator
# - test_async_gen_3_arg_deprecation_warning: athrow(type, value, traceback) is not supported
# - test_async_gen_api_01: __name__, __qualname__, ag_await, ag_frame, ag_running and ag_code
# - the other AsyncGenAsyncioTest cases, which need asyncio, sys.set_asyncgen_hooks or gc
import types
from collections.abc import AsyncGenerator, AsyncIterator


class AwaitException(Exception):
    pass


@types.coroutine
def awaitable(throw: bool = False):
    # Pystachy port: throw is a positional parameter (upstream's is keyword-only)
    if throw:
        yield ("throw",)
    else:
        yield ("result",)


def run_until_complete(coro) -> None:
    # Pystachy port: the value the coroutine returns is what its caller awaits (to_list)
    exc = False
    while True:
        try:
            if exc:
                exc = False
                fut = coro.throw(AwaitException)
            else:
                fut = coro.send(None)
        except StopIteration:
            return

        if fut == ("throw",):
            exc = True


async def iterate(gen, res: list[int]) -> None:
    async for i in gen:
        res.append(i)


def to_list(gen) -> list[int]:
    # Pystachy port: iterate() appends each item to the list that to_list() returns
    res: list[int] = []
    run_until_complete(iterate(gen, res))
    return res


async def show(aw) -> None:
    print("result", await aw)


def drive(aw) -> None:
    # Pystachy port: aw's own __next__() calls, which upstream makes, as a coroutine that awaits it
    c = show(aw)
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        pass


async def step(an, res: list[str]) -> None:
    res.append(str(await an))


def compare_generators(sync_gen, async_gen) -> list[str]:
    def sync_iterate(g) -> list[str]:
        res: list[str] = []
        while True:
            try:
                res.append(str(g.__next__()))
            except StopIteration:
                res.append('STOP')
                break
            except Exception as ex:
                res.append(type(ex).__name__)
        return res

    def async_iterate(g) -> list[str]:
        res: list[str] = []
        while True:
            an = step(g.__anext__(), res)
            try:
                while True:
                    try:
                        an.send(None)
                    except StopIteration:
                        break
                    except StopAsyncIteration:
                        raise
                    except Exception as ex:
                        res.append(type(ex).__name__)
                        break
            except StopAsyncIteration:
                res.append('STOP')
                break
        return res

    sync_gen_result = sync_iterate(sync_gen)
    async_gen_result = async_iterate(async_gen)
    print("assertEqual", sync_gen_result, async_gen_result, sync_gen_result == async_gen_result)
    return async_gen_result


def test_async_gen_iteration_01() -> None:
    async def gen():
        await awaitable()
        a = yield 123
        print("assertIs", a is None)
        await awaitable()
        yield 456
        await awaitable()
        yield 789

    print("assertEqual", to_list(gen()), [123, 456, 789])


def test_async_gen_iteration_02() -> None:
    async def gen():
        await awaitable()
        yield 123
        await awaitable()

    g = gen()
    ai = g.__aiter__()

    an = ai.__anext__()
    drive(an)

    an = ai.__anext__()
    try:
        drive(an)
    except StopAsyncIteration:
        print("StopAsyncIteration was raised")


def test_async_gen_exception_03() -> None:
    async def gen():
        await awaitable()
        yield 123
        await awaitable(True)
        yield 456

    try:
        to_list(gen())
    except AwaitException:
        print("assertRaises AwaitException")


def test_async_gen_exception_04() -> None:
    async def gen():
        await awaitable()
        yield 123
        1 / 0

    g = gen()
    ai = g.__aiter__()
    an = ai.__anext__()
    drive(an)

    try:
        drive(ai.__anext__())
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")


def test_async_gen_exception_05() -> None:
    async def gen():
        yield 123
        raise StopAsyncIteration

    try:
        to_list(gen())
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_async_gen_exception_06() -> None:
    async def gen():
        yield 123
        raise StopIteration

    try:
        to_list(gen())
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_async_gen_exception_07() -> None:
    def sync_gen():
        try:
            yield 1
            1 / 0
        finally:
            yield 2
            yield 3

        yield 100

    async def async_gen():
        try:
            yield 1
            1 / 0
        finally:
            yield 2
            yield 3

        yield 100

    compare_generators(sync_gen(), async_gen())


def test_async_gen_exception_08() -> None:
    def sync_gen():
        try:
            yield 1
        finally:
            yield 2
            1 / 0
            yield 3

        yield 100

    async def async_gen():
        try:
            yield 1
            await awaitable()
        finally:
            await awaitable()
            yield 2
            1 / 0
            yield 3

        yield 100

    compare_generators(sync_gen(), async_gen())


def test_async_gen_exception_09() -> None:
    def sync_gen():
        try:
            yield 1
            1 / 0
        finally:
            yield 2
            yield 3

        yield 100

    async def async_gen():
        try:
            await awaitable()
            yield 1
            1 / 0
        finally:
            yield 2
            await awaitable()
            yield 3

        yield 100

    compare_generators(sync_gen(), async_gen())


def test_async_gen_exception_10() -> None:
    # Pystachy port: asend(100) of an async generator whose send type is int | None (upstream's
    # __anext__().send(100))
    async def gen() -> AsyncGenerator[int, int | None]:
        yield 123
    try:
        gen().asend(100).send(None)
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


def test_async_gen_exception_11() -> None:
    def sync_gen():
        yield 10
        yield 20

    def sync_gen_wrapper():
        yield 1
        sg = sync_gen()
        sg.send(None)
        try:
            sg.throw(GeneratorExit())
        except GeneratorExit:
            yield 2
        yield 3

    async def async_gen():
        yield 10
        yield 20

    async def async_gen_wrapper():
        yield 1
        asg = async_gen()
        await asg.asend(None)
        try:
            await asg.athrow(GeneratorExit())
        except GeneratorExit:
            yield 2
        yield 3

    compare_generators(sync_gen_wrapper(), async_gen_wrapper())


async def gen12():
    # Pystachy port: test_async_gen_exception_12's gen, at module level, without the warning check;
    # me is ME[0], declared before gen12() compiles
    await anext(ME[0])
    yield 123


ME: list[AsyncIterator[int]] = []
ME.append(gen12())


def test_async_gen_exception_12() -> None:
    me = ME[0]
    ai = me.__aiter__()
    an = ai.__anext__()

    try:
        an.send(None)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)

    try:
        an.send(None)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


@types.coroutine
def _async_yield(v):
    return (yield v)


def test_async_gen_asend_close_runtime_error() -> None:
    async def agenfn():
        try:
            await _async_yield(None)
        except GeneratorExit:
            await _async_yield(None)
        return
        yield

    agen = agenfn()
    gen = agen.asend(None)
    gen.send(None)
    try:
        gen.close()
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


class MyExc(Exception):
    pass


def test_async_gen_athrow_close_runtime_error() -> None:
    async def agenfn():
        try:
            yield
        except MyExc:
            try:
                await _async_yield(None)
            except GeneratorExit:
                await _async_yield(None)

    agen = agenfn()
    try:
        agen.asend(None).send(None)
    except StopIteration:
        print("assertRaises StopIteration")
    gen = agen.athrow(MyExc)
    gen.send(None)
    try:
        gen.close()
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


@types.coroutine
def sleep():
    # Pystachy port: asyncio.sleep(0.01), as the driver below runs it: one yield of None
    yield


def run_until_done(coro) -> None:
    # Pystachy port: the event loop, for a coroutine that awaits nothing but sleep()
    try:
        while True:
            coro.send(None)
    except StopIteration:
        pass


async def arange(n):
    for i in range(n):
        await sleep()
        yield i


def make_arange(n):
    # This syntax is legal starting with Python 3.7
    return (i * 2 async for i in arange(n))


async def run_01(res: list[int]) -> None:
    # Pystachy port: the list is the caller's (upstream's run() returns it)
    res.extend([i async for i in make_arange(10)])


def test_async_gen_expression_01() -> None:
    res: list[int] = []
    run_until_done(run_01(res))
    print("assertEqual", res, [i * 2 for i in range(10)])


async def wrap(n):
    await sleep()
    return n


def make_arange_02(n):
    # This syntax is legal starting with Python 3.7
    return (i * 2 for i in range(n) if await wrap(i))


async def run_02(res: list[int]) -> None:
    res.extend([i async for i in make_arange_02(10)])


def test_async_gen_expression_02() -> None:
    res: list[int] = []
    run_until_done(run_02(res))
    print("assertEqual", res, [i * 2 for i in range(1, 10)])


async def async_iterate():
    yield 1
    yield 2


async def run_anext_twice() -> None:
    it = async_iterate()
    nxt = it.__anext__()
    await nxt
    try:
        await nxt
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)

    await it.aclose()  # prevent unfinished iterator warning


def test_async_gen_await_same_anext_coro_twice() -> None:
    run_until_done(run_anext_twice())


async def run_aclose_twice() -> None:
    it = async_iterate()
    nxt = it.aclose()
    await nxt
    try:
        await nxt
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_async_gen_await_same_aclose_coro_twice() -> None:
    run_until_done(run_aclose_twice())


test_async_gen_iteration_01()
test_async_gen_iteration_02()
test_async_gen_exception_03()
test_async_gen_exception_04()
test_async_gen_exception_05()
test_async_gen_exception_06()
test_async_gen_exception_07()
test_async_gen_exception_08()
test_async_gen_exception_09()
test_async_gen_exception_10()
test_async_gen_exception_11()
test_async_gen_exception_12()
test_async_gen_asend_close_runtime_error()
test_async_gen_athrow_close_runtime_error()
test_async_gen_expression_01()
test_async_gen_expression_02()
test_async_gen_await_same_anext_coro_twice()
test_async_gen_await_same_aclose_coro_twice()
