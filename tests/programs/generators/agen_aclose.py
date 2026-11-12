# aclose() of an async generator: GeneratorExit is raised where it is suspended, its finally blocks
# run, and their awaits suspend the coroutine that awaits aclose(); aclose() gives None once it
# finishes. A yield instead raises RuntimeError (it stays suspended there). Not started, suspended
# where nothing handles GeneratorExit, or finished: it is finished, and aclose() gives None.
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


async def plain():
    yield 1
    yield 2


async def cleanup():
    try:
        yield 1
        yield 2
    finally:
        print("finally")
        await tick("in finally")
        print("after await in finally")


async def ignorer():
    try:
        yield 1
    except GeneratorExit:
        print("ignoring")
        yield 2
    print("resumed after aclose")


async def catcher():
    try:
        yield 1
    except GeneratorExit:
        print("caught GeneratorExit")
        await tick("cleaning")


async def main() -> None:
    g = cleanup()
    async for x in g:
        print("item", x)
        break
    await g.aclose()
    print("closed")
    await g.aclose()
    print("closed again")


run(main(), "main")
g = plain()
run(g.aclose(), "aclose-new")
run(g.__anext__(), "after")
g = plain()
run(g.__anext__(), "s")
run(g.aclose(), "aclose-suspended")
run(g.__anext__(), "after")
g2 = ignorer()
run(g2.__anext__(), "s")
run(g2.aclose(), "aclose-ignorer")
run(g2.__anext__(), "after-ignorer")
g3 = catcher()
run(g3.__anext__(), "s")
run(g3.aclose(), "aclose-catcher")
run(g3.aclose(), "aclose-again")
