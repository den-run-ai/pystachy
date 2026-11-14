# async with (PEP 492): __aenter__ and __aexit__ are awaited; __aexit__ sees the exception that
# leaves the block, and a true result suppresses it; several items nest; break, continue and
# return leave the block through __aexit__(None, None, None)
import types


@types.coroutine
def tick(tag: str):
    yield tag


class CM:
    def __init__(self, name: str, suppress: bool) -> None:
        self.name = name
        self.suppress = suppress

    async def __aenter__(self) -> str:
        await tick("enter " + self.name)
        print("enter", self.name)
        return self.name.upper()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await tick("exit " + self.name)
        print("exit", self.name, exc_type is None, exc is None)
        return self.suppress


async def main() -> int:
    async with CM("a", False) as v:
        print("body", v)
    try:
        async with CM("b", False):
            raise ValueError("boom")
    except ValueError as e:
        print("caught", e)
    async with CM("c", True):
        raise KeyError("x")
    print("after suppress")
    async with CM("d", False) as x, CM("e", False) as y:
        print("nested", x, y)
    for k in range(3):
        async with CM("loop" + str(k), False):
            if k == 0:
                continue
            if k == 2:
                break
            print("loop body", k)
    for k in range(2):
        async with CM("r" + str(k), False):
            if k == 1:
                return k * 10
    return -1


c = main()
try:
    while True:
        print("yielded", c.send(None))
except StopIteration:
    print("done")
