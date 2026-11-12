# A module whose class has async methods, plain and special, for
# tests/programs/generators/coro_imported_methods.py
from types import TracebackType


class Box:
    def __init__(self, v: int) -> None:
        self.v = v
        self.i = 0

    async def get(self) -> int:
        return self.v

    async def __aenter__(self) -> int:
        print("enter", self.v)
        return self.v

    async def __aexit__(self, typ: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> bool:
        print("exit", typ is None)
        return False

    def __aiter__(self) -> "Box":
        return self

    async def __anext__(self) -> int:
        if self.i >= self.v:
            raise StopAsyncIteration
        self.i += 1
        return self.i


async def twice(x: int) -> int:
    return 2 * x
