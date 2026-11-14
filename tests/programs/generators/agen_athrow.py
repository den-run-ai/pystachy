# athrow(e) of an async generator: raised where it is suspended; what it yields then is athrow()'s
# value, and where it finishes, StopAsyncIteration. Not started, it finishes and e is raised as it
# is; suspended where nothing handles e, e leaves it (a StopIteration or StopAsyncIteration as
# RuntimeError); finished, athrow() gives None. The exception class or an exception object.
import types


@types.coroutine
def tick(v: str):
    yield v


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
    except ValueError as e:
        print(label, "ValueError", e)


async def plain():
    yield 1
    yield 2


async def guarded():
    try:
        yield 1
    except ValueError as e:
        print("caught", repr(e))
        await tick("handling")
        yield 10
    yield 20


async def main() -> None:
    g = guarded()
    print(await g.__anext__())
    print(await g.athrow(ValueError("v")))
    print(await g.__anext__())
    try:
        await g.athrow(ValueError)
    except ValueError:
        print("not caught twice")
    print(await g.athrow(ValueError))
    h = guarded()
    print(await h.__anext__())
    print(await h.__anext__())
    try:
        await h.athrow(KeyError)
    except KeyError:
        print("KeyError leaves it")


run(main(), "main")
g = plain()
run(g.athrow(ValueError("x")), "athrow-new")
run(g.__anext__(), "after")
g = plain()
run(g.__anext__(), "s")
run(g.athrow(StopIteration), "athrow-SI")
g = plain()
run(g.__anext__(), "s")
run(g.athrow(StopAsyncIteration), "athrow-SAI")
g = plain()
run(g.__anext__(), "s")
run(g.athrow(ValueError), "athrow-VE")
run(g.athrow(ValueError), "athrow-finished")
g2 = guarded()
run(g2.__anext__(), "s")
run(g2.athrow(ValueError), "athrow-caught")
run(g2.__anext__(), "next")
run(g2.__anext__(), "end")
