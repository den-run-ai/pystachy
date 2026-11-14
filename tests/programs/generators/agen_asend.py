# asend(v) of an async generator annotated AsyncGenerator[T, S]: its yield's value is what asend()
# sends (None from __anext__()); a just-started one takes only None. Its awaitable used as a value:
# awaited later, sent None by a driver, and awaited again (CPython's RuntimeError).
from collections.abc import AsyncGenerator


async def echo() -> AsyncGenerator[str, str | None]:
    got = yield "first"
    while got is not None:
        got = yield "echo " + got


def run(c, label: str) -> None:
    try:
        while True:
            print(label, "driver got", c.send(None))
    except StopIteration:
        print(label, "stop")
    except StopAsyncIteration:
        print(label, "StopAsyncIteration")
    except RuntimeError as e:
        print(label, "RuntimeError", e)
    except TypeError as e:
        print(label, "TypeError", e)


async def talk() -> None:
    e = echo()
    print(await e.asend(None))
    print(await e.asend("a"))
    print(await e.asend("b"))
    try:
        await e.__anext__()
    except StopAsyncIteration:
        print("echo done")


run(talk(), "talk")
e = echo()
run(e.asend("early"), "early")
a = e.asend(None)
run(a, "first")
run(a, "again")
run(e.asend("x"), "x")
run(e.asend(None), "end")
run(e.asend("after"), "after")
