# error: await of a generator held in a variable is not supported: await the call of its @types.coroutine generator function
import types


@types.coroutine
def tick():
    yield


async def run() -> None:
    g = tick()
    await g


run().send(None)
