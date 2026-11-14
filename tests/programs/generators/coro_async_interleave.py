# Coroutines that suspend inside async with's exception handling: each resumes with its own
# exception; __aexit__ raising; close() and throw() of a coroutine suspended in the block
import types
from collections.abc import Coroutine


@types.coroutine
def tick(tag: str):
    yield tag


class Slow:
    def __init__(self, name: str) -> None:
        self.name = name

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # suspends while handling the exception: another task runs meanwhile
        await tick(self.name + " exiting")
        await tick(self.name + " exiting again")
        print(self.name, "saw", exc_type.__name__ if exc_type is not None else None, exc)
        return False


async def worker(name: str, err: str) -> str:
    try:
        async with Slow(name):
            await tick(name + " body")
            raise ValueError(err)
    except ValueError as e:
        print(name, "propagated", e)
        return name + " ok"
    return name + " unreached"


def run_all(cs: list[Coroutine[str | None, None, str]]) -> None:
    alive = list(cs)
    while len(alive) > 0:
        nxt = []
        for c in alive:
            try:
                print("  ", c.send(None))
                nxt.append(c)
            except StopIteration:
                print("  finished")
        alive = nxt


run_all([worker("A", "a-err"), worker("B", "b-err")])


class Chain:
    async def __aenter__(self):
        return 1

    async def __aexit__(self, exc_type, exc, tb):
        raise KeyError("from aexit")


async def chained() -> None:
    try:
        async with Chain():
            raise ValueError("inner")
    except KeyError as e:
        print("KeyError", e)


c = chained()
try:
    c.send(None)
except StopIteration:
    pass


class Logged:
    def __init__(self, name: str) -> None:
        self.name = name

    async def __aenter__(self):
        print("enter", self.name)

    async def __aexit__(self, exc_type, exc, tb):
        print("exit", self.name, exc_type.__name__ if exc_type is not None else None)


async def held() -> None:
    async with Logged("held"):
        await tick("inside")
        print("not reached")


h = held()
print(h.send(None))
h.close()
print("closed")
h2 = held()
print(h2.send(None))
try:
    h2.throw(IndexError("thrown"))
except IndexError as e:
    print("IndexError out:", e)


class Pairs:
    def __init__(self) -> None:
        self.k = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> tuple[int, str]:
        self.k += 1
        if self.k > 3:
            raise StopAsyncIteration
        return self.k, "v" + str(self.k)


async def loops() -> None:
    async for a, b in Pairs():
        async with Logged(b):
            if a == 2:
                continue
            print("pair", a, b)
    try:
        async for a, b in Pairs():
            raise StopAsyncIteration
    except StopAsyncIteration:
        print("body's StopAsyncIteration propagates")


c3 = loops()
try:
    c3.send(None)
except StopIteration:
    pass
