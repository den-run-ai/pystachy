# A StopAsyncIteration or StopIteration that leaves an async generator's body is RuntimeError (PEP
# 525, PEP 479), with the exception as its __cause__; one that it raises and catches itself, or
# that an await of a coroutine raises into it, is no end of the iteration. An async generator that
# returns ends it, as falling off its end does.
async def raises_sai():
    yield 1
    raise StopAsyncIteration


async def raises_si():
    yield 1
    raise StopIteration


async def handles():
    try:
        raise StopAsyncIteration
    except StopAsyncIteration:
        yield "handled"
    yield "after"


async def stops(n: int):
    for i in range(10):
        if i == n:
            return
        yield i


async def fails() -> int:
    raise StopAsyncIteration


async def awaits_failure():
    yield 0
    await fails()


async def main() -> None:
    for g in [raises_sai(), raises_si()]:
        try:
            async for x in g:
                print("got", x)
        except RuntimeError as e:
            print("RuntimeError", e, type(e.__cause__).__name__)
    async for s in handles():
        print(s)
    async for i in stops(2):
        print("stops", i)
    try:
        async for i in awaits_failure():
            print("awaits", i)
    except RuntimeError as e:
        print("RuntimeError", e)


c = main()
try:
    c.send(None)
except StopIteration:
    print("done")
