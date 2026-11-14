# async for ends at the builtin StopAsyncIteration, whatever a local of its name holds


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


async def before() -> None:
    StopAsyncIteration = ValueError
    async for x in Ticks(2):
        print("item", x)
    else:
        print("exhausted")
    print("before", StopAsyncIteration.__name__)


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass


run(before())
