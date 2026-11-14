# error: mixed() yields int to the code that runs it, but awaits text(), which yields str
import types


@types.coroutine
def number():
    yield 1


@types.coroutine
def text():
    yield "a"


async def mixed() -> None:
    await number()
    await text()


mixed().send(None)
