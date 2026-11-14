# Adapted from CPython 3.13.16 Lib/test/test_coroutines.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91: CoroutineTest's test_with_1 to test_with_13,
# test_for_1, test_for_2, test_for_3, test_for_4, test_for_6, test_for_7, test_for_8,
# test_for_assign_raising_stop_async_iteration's run_for, test_comp_1 and test_comp_2.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) and assertRaises print
# what they check, so the recording holds the values. run_async(coro) runs the coroutine as
# upstream's does, printing each value it yields; the value it returns, which upstream takes from
# StopIteration's args, is printed by result_of(), a coroutine that awaits it. The classes the tests
# define are the module's, numbered by test (Pystachy compiles no class inside a function), and
# their nonlocal counters are globals. Values that upstream yields or collects in one list are of
# one type here: test_with_1 yields 'managers A B' for ('managers', 'A', 'B'), test_for_1's buffers
# hold strs, and test_comp_2's awaited lists are of one item type; test_with_5 raises the
# AssertionError that upstream's assertEqual((1,), 1) raises; test_with_12 prints type(cm).__name__
# for its assertIs(cm.__class__, CM); run_for's async iterator is a class for upstream's async
# generator source().
# EXCLUDED upstream checks and cases:
# - exceptions' __context__ and __cause__ (test_with_7, test_with_10, test_with_11, test_for_11),
#   sys.getrefcount() (test_for_2, test_for_3, test_for_4, test_for_6) and warnings filters
#   (test_for_6, test_for_8): not supported
# - test_for_11 (an __await__ that is no generator), test_for_tuple and test_for_stop_iteration
#   (async iterators that subclass tuple and StopIteration), the run_list and run_gen parts of
#   test_for_assign_raising_stop_async_iteration and test_for_assign_raising_stop_async_iteration_2
#   (asynchronous comprehensions and async generators, rejected as the program compiles), test_comp_3
#   to test_comp_10 (asynchronous comprehensions and async generators) and test_copy (copy, pickle)
import types


class AsyncYieldFrom:
    def __init__(self, obj):
        self.obj = obj

    def __await__(self):
        yield from self.obj


class AsyncYield:
    def __init__(self, value):
        self.value = value

    def __await__(self):
        yield self.value


async def result_of(coro):
    print("result", await coro)


def run_async(coro) -> None:
    c = result_of(coro)
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        pass


class Manager1:
    def __init__(self, name):
        self.name = name

    async def __aenter__(self):
        await AsyncYieldFrom(['enter-1-' + self.name,
                              'enter-2-' + self.name])
        return self

    async def __aexit__(self, *args):
        await AsyncYieldFrom(['exit-1-' + self.name,
                              'exit-2-' + self.name])

        if self.name == 'B':
            return True


def test_with_1() -> None:
    async def foo():
        async with Manager1("A") as a, Manager1("B") as b:
            await AsyncYieldFrom(['managers ' + a.name + ' ' + b.name])
            1/0

    run_async(foo())

    async def foo2():
        async with Manager1("A") as a, Manager1("C") as c:
            await AsyncYieldFrom(['managers ' + a.name + ' ' + c.name])
            1/0

    try:
        run_async(foo2())
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")


class CM2:
    def __aenter__(self):
        pass


body_executed = False


def test_with_2() -> None:
    async def foo():
        global body_executed
        body_executed = False
        async with CM2():
            body_executed = True

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)
    print("assertIs", body_executed, False)


class CM3:
    def __aexit__(self):
        pass


def test_with_3() -> None:
    async def foo():
        global body_executed
        body_executed = False
        async with CM3():
            body_executed = True

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)
    print("assertIs", body_executed, False)


class CM4:
    pass


def test_with_4() -> None:
    async def foo():
        global body_executed
        body_executed = False
        async with CM4():
            body_executed = True

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)
    print("assertIs", body_executed, False)


class CM5:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass


def test_with_5() -> None:
    async def func():
        async with CM5():
            raise AssertionError("(1,) != 1")

    try:
        run_async(func())
    except AssertionError:
        print("assertRaises AssertionError")


class CM6:
    def __aenter__(self):
        return 123

    def __aexit__(self, *e):
        return 456


def test_with_6() -> None:
    async def foo():
        async with CM6():
            pass

    try:
        # it's important that __aexit__ wasn't called
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


class CM7:
    async def __aenter__(self):
        return self

    def __aexit__(self, *e):
        return 444


def test_with_7() -> None:
    # Exit with exception
    async def foo():
        async with CM7():
            1/0

    try:
        run_async(foo())
    except TypeError as exc:
        print("assertRegex", exc)
    else:
        print('invalid asynchronous context manager did not fail')


CNT = 0


class CM8:
    async def __aenter__(self):
        return self

    def __aexit__(self, *e):
        return 456


def test_with_8() -> None:
    # Normal exit
    async def foo():
        global CNT
        async with CM8():
            CNT += 1
    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)
    print("assertEqual", CNT, 1)

    # Exit with 'break'
    async def foo2():
        global CNT
        for i in range(2):
            async with CM8():
                CNT += 1
                break
    try:
        run_async(foo2())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)
    print("assertEqual", CNT, 2)

    # Exit with 'continue'
    async def foo3():
        global CNT
        for i in range(2):
            async with CM8():
                CNT += 1
                continue
    try:
        run_async(foo3())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)
    print("assertEqual", CNT, 3)

    # Exit with 'return'
    async def foo4():
        global CNT
        async with CM8():
            CNT += 1
            return
    try:
        run_async(foo4())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)
    print("assertEqual", CNT, 4)


class CM9:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *e):
        1/0


def test_with_9() -> None:
    global CNT
    CNT = 0

    async def foo():
        global CNT
        async with CM9():
            CNT += 1

    try:
        run_async(foo())
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")

    print("assertEqual", CNT, 1)


def test_with_10() -> None:
    async def foo():
        async with CM9():
            async with CM9():
                raise RuntimeError

    try:
        run_async(foo())
    except ZeroDivisionError as exc:
        print("ZeroDivisionError", exc)
    else:
        print('exception from __aexit__ did not propagate')


class CM11:
    async def __aenter__(self):
        raise NotImplementedError

    async def __aexit__(self, *e):
        1/0


def test_with_11() -> None:
    async def foo():
        async with CM11():
            raise RuntimeError

    try:
        run_async(foo())
    except NotImplementedError:
        print("NotImplementedError")
    else:
        print('exception from __aenter__ did not propagate')


class CM12:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *e):
        return True


def test_with_12() -> None:
    async def foo():
        async with CM12() as cm:
            print("assertIs", type(cm).__name__, "CM12")
            raise RuntimeError

    run_async(foo())


class CM13:
    async def __aenter__(self):
        1/0

    async def __aexit__(self, *e):
        return True


def test_with_13() -> None:
    global CNT
    CNT = 0

    async def foo():
        global CNT
        CNT += 1
        async with CM13():
            CNT += 1000
        CNT += 10000

    try:
        run_async(foo())
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")
    print("assertEqual", CNT, 1)


aiter_calls = 0


class AsyncIter1:
    def __init__(self):
        self.i = 0

    def __aiter__(self):
        global aiter_calls
        aiter_calls += 1
        return self

    async def __anext__(self):
        self.i += 1

        if not (self.i % 10):
            await AsyncYield(self.i * 10)

        if self.i > 100:
            raise StopAsyncIteration

        return self.i, self.i


def test_for_1() -> None:
    buffer: list[str] = []

    async def test1():
        async for i1, i2 in AsyncIter1():
            buffer.append(str(i1 + i2))

    run_async(test1())
    # Make sure that __aiter__ was called only once
    print("assertEqual", aiter_calls, 1)
    print("assertEqual", buffer == [str(i*2) for i in range(1, 101)])

    buffer.clear()

    async def test2():
        async for i in AsyncIter1():
            buffer.append(str(i[0]))
            if i[0] == 20:
                break
        else:
            buffer.append('what?')
        buffer.append('end')

    run_async(test2())
    # Make sure that __aiter__ was called only once
    print("assertEqual", aiter_calls, 2)
    print("assertEqual", buffer)

    buffer.clear()

    async def test3():
        async for i in AsyncIter1():
            if i[0] > 20:
                continue
            buffer.append(str(i[0]))
        else:
            buffer.append('what?')
        buffer.append('end')

    run_async(test3())
    # Make sure that __aiter__ was called only once
    print("assertEqual", aiter_calls, 3)
    print("assertEqual", buffer)


def test_for_2() -> None:
    tup = (1, 2, 3)

    async def foo():
        async for i in tup:
            print('never going to happen')

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


class I3:
    def __aiter__(self):
        return self


def test_for_3() -> None:
    aiter = I3()

    async def foo():
        async for i in aiter:
            print('never going to happen')

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


class I4:
    def __aiter__(self):
        return self

    def __anext__(self):
        return ()


def test_for_4() -> None:
    aiter = I4()

    async def foo():
        async for i in aiter:
            print('never going to happen')

    try:
        run_async(foo())
    except TypeError as e:
        print("assertRaisesRegex TypeError", e)


I = 0


class Manager6:
    async def __aenter__(self):
        global I
        I += 10000

    async def __aexit__(self, *args):
        global I
        I += 100000


class Iterable6:
    def __init__(self):
        self.i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.i > 10:
            raise StopAsyncIteration
        self.i += 1
        return self.i


def test_for_6() -> None:
    manager = Manager6()
    iterable = Iterable6()

    async def main():
        global I

        async with manager:
            async for i in iterable:
                I += 1
        I += 1000

    run_async(main())
    print("assertEqual", I, 111011)

    async def main2():
        global I

        async with Manager6():
            async for i in Iterable6():
                I += 1
        I += 1000

        async with Manager6():
            async for i in Iterable6():
                I += 1
        I += 1000

    run_async(main2())
    print("assertEqual", I, 333033)

    async def main3():
        global I

        async with Manager6():
            I += 100
            async for i in Iterable6():
                I += 1
            else:
                I += 10000000
        I += 1000

        async with Manager6():
            I += 100
            async for i in Iterable6():
                I += 1
            else:
                I += 10000000
        I += 1000

    run_async(main3())
    print("assertEqual", I, 20555255)


class AI7:
    def __aiter__(self):
        1/0


def test_for_7() -> None:
    global CNT
    CNT = 0

    async def foo():
        global CNT
        async for i in AI7():
            CNT += 1
        CNT += 10

    try:
        run_async(foo())
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")
    print("assertEqual", CNT, 0)


def test_for_8() -> None:
    global CNT
    CNT = 0

    async def foo():
        global CNT
        async for i in AI7():
            CNT += 1
        CNT += 10

    try:
        run_async(foo())
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")
    print("assertEqual", CNT, 0)


class BadTarget:
    def __setitem__(self, key, value):
        raise StopAsyncIteration(42)


class Source:
    def __init__(self):
        self.done = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.done:
            raise StopAsyncIteration
        self.done = True
        return 10


def test_for_assign_raising_stop_async_iteration() -> None:
    tgt = BadTarget()

    async def run_for():
        try:
            async for tgt[0] in Source():
                pass
        except StopAsyncIteration as e:
            print("assertRaises StopAsyncIteration", e)
        return 'end'

    run_async(run_for())


async def f(i):
    return i


def test_comp_1() -> None:
    async def run_list():
        return [await c for c in [f(1), f(41)]]

    async def run_set():
        return sorted({await c for c in [f(1), f(41)]})

    async def run_dict1():
        return {await c: 'a' for c in [f(1), f(41)]}

    async def run_dict2():
        return {i: await c for i, c in enumerate([f(1), f(41)])}

    run_async(run_list())
    run_async(run_set())
    run_async(run_dict1())
    run_async(run_dict2())


def test_comp_2() -> None:
    async def run_list():
        return [s for c in [f(''), f('abc'), f('')]
                for s in await c]

    run_async(run_list())

    async def run_set():
        return sorted({d
                       for c in [f([f([10, 30]),
                                    f([20])])]
                       for s in await c
                       for d in await s})

    run_async(run_set())

    async def run_set2():
        return sorted({await s
                       for c in [f([f(10), f(20)])]
                       for s in await c})

    run_async(run_set2())


test_with_1()
test_with_2()
test_with_3()
test_with_4()
test_with_5()
test_with_6()
test_with_7()
test_with_8()
test_with_9()
test_with_10()
test_with_11()
test_with_12()
test_with_13()
test_for_1()
test_for_2()
test_for_3()
test_for_4()
test_for_6()
test_for_7()
test_for_8()
test_for_assign_raising_stop_async_iteration()
test_comp_1()
test_comp_2()
