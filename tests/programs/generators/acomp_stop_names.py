# An asynchronous comprehension, and an asynchronous generator expression, over an object of a class
# with __anext__ end at the builtin StopAsyncIteration, whatever the program's global of that name
# holds (here ValueError: an __anext__ that raises it leaves the comprehension, as in CPython), and
# whatever a local of that name holds, or will hold.
from asyncstop_ticks import Ticks

StopAsyncIteration = ValueError


class Rebound:
    def __aiter__(self) -> "Rebound":
        return self

    async def __anext__(self) -> int:
        raise StopAsyncIteration


async def builtin_end() -> None:
    print([x async for x in Ticks(2)], StopAsyncIteration.__name__)
    print([x async for x in (y * 10 async for y in Ticks(3))])


async def local_end() -> None:
    StopAsyncIteration = KeyError
    print([x async for x in Ticks(1)], StopAsyncIteration.__name__)


async def late_end() -> None:
    print({x async for x in Ticks(2)})
    StopAsyncIteration = KeyError
    print(StopAsyncIteration.__name__)


async def rebound_end() -> None:
    print([x async for x in Rebound()])
    print("not reached")


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass
    except Exception as e:
        print(type(e).__name__, "left the comprehension")


run(builtin_end())
run(local_end())
run(late_end())
run(rebound_end())
