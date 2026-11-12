# async for never reads a variable named StopAsyncIteration: a local of that name assigned only
# after the loop is not read before its assignment


class Ticks:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __aiter__(self) -> "Ticks":
        return self

    async def __anext__(self) -> int:
        if self.i >= self.n:
            raise StopAsyncIteration
        self.i += 1
        return self.i


async def after() -> None:
    async for x in Ticks(2):
        print("item", x)
    StopAsyncIteration = KeyError
    print("after", StopAsyncIteration.__name__)


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass


run(after())
