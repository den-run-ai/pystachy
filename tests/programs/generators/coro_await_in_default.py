# The defaults of a def or lambda that a coroutine defines are evaluated by the coroutine, where
# an await in them suspends it: the coroutine is no async def that never suspends
import types


@types.coroutine
def pause():
    yield "paused"


async def step() -> int:
    await pause()
    return 5


async def with_def() -> int:
    def inner(x: int = await step()) -> int:
        return x
    return inner()


async def with_lambda() -> int:
    g = lambda x=(await step()): x + 1
    return g()


async def main() -> None:
    print(await with_def())
    print(await with_lambda())


c = main()
try:
    while True:
        print("yielded", c.send(None))
except StopIteration:
    pass
