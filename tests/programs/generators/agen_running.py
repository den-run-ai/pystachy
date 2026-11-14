# While a step of an async generator is suspended where one of its awaits suspends it, another
# step raises RuntimeError: anext(), asend(), athrow() and aclose() each name themselves. An
# awaitable of a method that has finished or failed cannot be awaited again (CPython's two
# messages). A step that resumes the async generator from its own code is one of those.
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


async def slow():
    yield 1
    await tick("waiting")
    yield 2


g = slow()
run(g.__anext__(), "first")
a = g.__anext__()
print(a.send(None))
run(g.__anext__(), "anext")
run(g.asend(None), "asend")
t = g.athrow(ValueError)
run(t, "athrow")
c = g.aclose()
run(c, "aclose")
run(t, "athrow-again")
run(c, "aclose-again")
run(a, "rest")
run(a, "rest-again")


async def selfish():
    yield 1
    print("inner", await anext(SELF[0]))
    yield 2


SELF = [selfish()]
run(anext(SELF[0]), "outer")
run(anext(SELF[0]), "nested")
