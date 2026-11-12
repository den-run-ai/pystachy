# error: asynchronous comprehensions are not supported
class Ticks:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __aiter__(self):
        return self

    async def __anext__(self) -> int:
        if self.i >= self.n:
            raise StopAsyncIteration
        self.i += 1
        return self.i


async def total(t: Ticks) -> int:
    return sum([i async for i in t])


total(Ticks(3)).send(None)
