# isinstance(x, types.CoroutineType) is decided by x's type as the program compiles: true for
# the coroutine of an async def, false for an object or a generator, so that a function given
# either can take the coroutine's branch only for a coroutine (asyncio.ensure_future() does).
import types
from types import CoroutineType


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


async def answer() -> int:
    return 42


def gen():
    yield 1


def kind(x) -> str:
    if isinstance(x, Box):
        return "box " + str(x.v)
    if isinstance(x, types.CoroutineType):
        try:
            x.send(None)
        except StopIteration:
            pass
        return "coroutine"
    return "other"


def named(x) -> bool:
    return isinstance(x, CoroutineType)


c = answer()
print(kind(Box(1)), kind(c), kind(3), kind("s"))
print(named(Box(2)), named(gen()), named(1.5))
d = answer()
print(named(d))
d.close()
