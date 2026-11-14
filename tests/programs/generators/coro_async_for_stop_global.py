# async for ends at the builtin StopAsyncIteration, whatever the program's global of its name
# holds: here ValueError, which ends no loop and leaves it, as in CPython
from asyncstop_ticks import Ticks

StopAsyncIteration = ValueError


class Rebound:
    def __aiter__(self) -> "Rebound":
        return self

    async def __anext__(self) -> int:
        raise StopAsyncIteration


async def builtin_end() -> None:
    async for x in Ticks(2):
        print("item", x)
    else:
        print("exhausted")
    print("global", StopAsyncIteration.__name__)


async def rebound_end() -> None:
    async for x in Rebound():
        print("item", x)
    print("not reached")


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass
    except Exception as e:
        print(type(e).__name__, "left the loop")


run(builtin_end())
run(rebound_end())
