# An asynchronous iterator that ends with the builtin StopAsyncIteration, for a program that
# binds that name to something else (tests/programs/generators/coro_async_for_stop_global.py)


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
