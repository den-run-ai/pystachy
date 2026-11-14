# CPython 3.13's TypeErrors where async with and async for meet objects without the protocol:
# no __aenter__, no __aexit__ (checked before __aenter__ runs), results that are not awaitable, None
# (also of a class's type) and objects of builtin types
def run(c) -> None:
    try:
        while True:
            c.send(None)
    except StopIteration:
        pass
    except TypeError as e:
        print("TypeError:", e)


class NoEnter:
    async def __aexit__(self, *a):
        pass


class NoExit:
    async def __aenter__(self):
        print("aenter ran")


class BadEnter:
    def __aenter__(self):
        return 1

    async def __aexit__(self, *a):
        pass


class BadExit:
    async def __aenter__(self):
        return 1

    def __aexit__(self, *a):
        return 2


class NoAiter:
    pass


class AiterNoAnext:
    def __aiter__(self):
        return 5


class BadAnext:
    def __aiter__(self):
        return self

    def __anext__(self):
        return 7


async def w1():
    async with NoEnter():
        print("body")


async def w2():
    async with NoExit():
        print("body")


async def w3():
    async with BadEnter():
        print("body")


async def w4():
    async with BadExit():
        print("body")


async def w5():
    async with None:
        print("body")


async def w6():
    async with 5:
        print("body")


async def w7(m: NoExit | None):
    async with m:
        print("body")


async def f1():
    async for x in NoAiter():
        print(x)


async def f2():
    async for x in AiterNoAnext():
        print(x)


async def f3():
    async for x in BadAnext():
        print(x)


async def f4():
    async for x in None:
        print(x)


async def f5():
    async for x in [1, 2]:
        print(x)


run(w1())
run(w2())
run(w3())
run(w4())
run(w5())
run(w6())
run(w7(None))
run(f1())
run(f2())
run(f3())
run(f4())
run(f5())
