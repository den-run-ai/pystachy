# Coroutines that never suspend (docs/internals.md#coroutines): an await of a call of one, by its
# name, calls its synchronous twin (@f.fib.sync.*), an ordinary function, so fib() compiles to no
# coroutine at all; a coroutine whose await reaches a @types.coroutine generator suspends and stays
# a coroutine (presplitcoroutine), as do the generator and main(), whose call is used as a value.
import types


@types.coroutine
def pause():
    yield


async def fib(n: int) -> int:
    if n <= 1:
        return n
    return await fib(n - 1) + await fib(n - 2)


async def waits(n: int) -> int:
    await pause()
    return n


async def main() -> int:
    return await fib(10) + await waits(1)


c = main()
c.send(None)
