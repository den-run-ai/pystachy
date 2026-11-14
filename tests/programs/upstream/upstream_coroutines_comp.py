# Adapted from CPython 3.13.16 Lib/test/test_coroutines.py (SHA-256
# 161fbe91f6a7c92cdc887a4c824e6c76b33eb7bae449e58203c6ef98960279e5), commit
# cbc944f4bc59639a444dd971c737788ba2283a91: CoroutineTest's test_comp_3 to test_comp_10 and
# test_nested_comp (test_comp_1 and test_comp_2 are upstream_coroutines_with_for.py's).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) and assertRaises print
# what they check, so the recording holds the values. run_async(coro) runs the coroutine as
# upstream's does, printing each value it yields; the value it returns, which upstream takes from
# StopIteration's args, is printed by result_of(), a coroutine that awaits it. The classes the tests
# define are the module's (Pystachy compiles no class inside a function). test_comp_6's tuples
# are lists.
# EXCLUDED upstream cases:
# - the run_list and run_gen parts of test_for_assign_raising_stop_async_iteration and its _2,
#   whose targets' assignment always raises (a __setitem__ and an __iter__ that raise): Pystachy
#   infers no element type for the comprehension, and no iterator type for __iter__; they also
#   check exception args and __cause__ (the run_for parts are upstream_coroutines_with_for.py's)
async def asynciter(iterable):
    """Convert an iterable to an asynchronous iterator."""
    for x in iterable:
        yield x


async def result_of(coro):
    print("result", await coro)


def run_async(coro) -> None:
    c = result_of(coro)
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        pass


def test_comp_3() -> None:
    async def f(it):
        for i in it:
            yield i

    async def run_list():
        return [i + 1 async for i in f([10, 20])]
    run_async(run_list())

    async def run_set():
        return {i + 1 async for i in f([10, 20])}
    run_async(run_set())

    async def run_dict():
        return {i + 1: i + 2 async for i in f([10, 20])}
    run_async(run_dict())

    async def run_gen():
        gen = (i + 1 async for i in f([10, 20]))
        return [g + 100 async for g in gen]
    run_async(run_gen())


def test_comp_4() -> None:
    async def f(it):
        for i in it:
            yield i

    async def run_list():
        return [i + 1 async for i in f([10, 20]) if i > 10]
    run_async(run_list())

    async def run_set():
        return {i + 1 async for i in f([10, 20]) if i > 10}
    run_async(run_set())

    async def run_dict():
        return {i + 1: i + 2 async for i in f([10, 20]) if i > 10}
    run_async(run_dict())

    async def run_gen():
        gen = (i + 1 async for i in f([10, 20]) if i > 10)
        return [g + 100 async for g in gen]
    run_async(run_gen())


def test_comp_4_2() -> None:
    async def f(it):
        for i in it:
            yield i

    async def run_list():
        return [i + 10 async for i in f(range(5)) if 0 < i < 4]
    run_async(run_list())

    async def run_set():
        return {i + 10 async for i in f(range(5)) if 0 < i < 4}
    run_async(run_set())

    async def run_dict():
        return {i + 10: i + 100 async for i in f(range(5)) if 0 < i < 4}
    run_async(run_dict())

    async def run_gen():
        gen = (i + 10 async for i in f(range(5)) if 0 < i < 4)
        return [g + 100 async for g in gen]
    run_async(run_gen())


def test_comp_5() -> None:
    async def f(it):
        for i in it:
            yield i

    async def run_list():
        return [i + 1 for pair in ([10, 20], [30, 40]) if pair[0] > 10
                async for i in f(pair) if i > 30]
    run_async(run_list())


def test_comp_6() -> None:
    async def f(it):
        for i in it:
            yield i

    async def run_list():
        # Pystachy port: lists for upstream's tuples (10, 20) and (30,), as a list holds one type
        return [i + 1 async for seq in f([[10, 20], [30]])
                for i in seq]

    run_async(run_list())


def test_comp_7() -> None:
    async def f():
        yield 1
        yield 2
        raise Exception('aaa')

    async def run_list():
        return [i async for i in f()]

    try:
        run_async(run_list())
    except Exception as e:
        print("assertRaisesRegex Exception", e)


def test_comp_8() -> None:
    async def f():
        return [i for i in [1, 2, 3]]

    run_async(f())


def test_comp_9() -> None:
    async def gen():
        yield 1
        yield 2

    async def f():
        l = [i async for i in gen()]
        return [i for i in l]

    run_async(f())


def test_comp_10() -> None:
    async def f():
        xx = {i for i in [1, 2, 3]}
        return {x: x for x in xx}

    run_async(f())


def test_nested_comp() -> None:
    async def run_list_inside_list():
        return [[i + j async for i in asynciter([1, 2])] for j in [10, 20]]
    run_async(run_list_inside_list())

    async def run_set_inside_list():
        return [{i + j async for i in asynciter([1, 2])} for j in [10, 20]]
    run_async(run_set_inside_list())

    async def run_list_inside_set():
        return {sum([i async for i in asynciter(range(j))]) for j in [3, 5]}
    run_async(run_list_inside_set())

    async def run_dict_inside_dict():
        return {j: {i: i + j async for i in asynciter([1, 2])} for j in [10, 20]}
    run_async(run_dict_inside_dict())

    async def run_list_inside_gen():
        gen = ([i + j async for i in asynciter([1, 2])] for j in [10, 20])
        return [x async for x in gen]
    run_async(run_list_inside_gen())

    async def run_gen_inside_list():
        gens = [(i async for i in asynciter(range(j))) for j in [3, 5]]
        return [x for g in gens async for x in g]
    run_async(run_gen_inside_list())

    async def run_gen_inside_gen():
        gens = ((i async for i in asynciter(range(j))) for j in [3, 5])
        return [x for g in gens async for x in g]
    run_async(run_gen_inside_gen())

    async def run_list_inside_list_inside_list():
        return [[[i + j + k async for i in asynciter([1, 2])]
                 for j in [10, 20]]
                for k in [100, 200]]
    run_async(run_list_inside_list_inside_list())


test_comp_3()
test_comp_4()
test_comp_4_2()
test_comp_5()
test_comp_6()
test_comp_7()
test_comp_8()
test_comp_9()
test_comp_10()
test_nested_comp()
