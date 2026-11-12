# The builtins aiter() and anext() (with and without a default) of objects of classes with
# __aiter__ and __anext__, and of async generators; their TypeErrors for objects that are none.
# anext()'s default ends at the builtin StopAsyncIteration, whatever the program binds to its name.
class Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __aiter__(self):
        return self

    async def __anext__(self) -> int:
        if self.n == 0:
            raise StopAsyncIteration
        self.n -= 1
        return self.n


class Iterable:
    def __aiter__(self) -> Countdown:
        return Countdown(2)


class Bad:
    def __aiter__(self) -> int:
        return 1


async def letters():
    yield "x"


async def main() -> None:
    c = Countdown(2)
    print(aiter(c) is c)
    print(await anext(c), await anext(c, -1), await anext(c, -1))
    try:
        await anext(c)
    except StopAsyncIteration:
        print("StopAsyncIteration")
    it = aiter(Iterable())
    print(await anext(it), await anext(it))
    g = letters()
    a = anext(g, "none")
    print(await a, await anext(g, "none"))
    try:
        aiter(5)
    except TypeError as e:
        print(e)
    try:
        anext(5)
    except TypeError as e:
        print(e)
    try:
        aiter(Bad())
    except TypeError as e:
        print(e)


async def rebinds() -> None:
    StopAsyncIteration = KeyError
    d = Countdown(1)
    print(await anext(d, 10), await anext(d, 20), StopAsyncIteration.__name__)
    e = Countdown(1)
    print(await anext(e, None), await anext(e, None))


for co in [main(), rebinds()]:
    try:
        co.send(None)
    except StopIteration:
        print("done")
