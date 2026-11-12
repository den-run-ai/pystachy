# A program's own functions named anext and aiter are what those names call, also in an await,
# where the builtins of those names would run an async generator's step.
async def letters():
    yield "x"


async def anext(g) -> str:
    return "own anext"


def aiter(x: int) -> int:
    return x * 2


async def main() -> None:
    g = letters()
    print(await anext(g), aiter(2))
    async for s in g:
        print(s)


co = main()
try:
    co.send(None)
except StopIteration:
    print("done")
