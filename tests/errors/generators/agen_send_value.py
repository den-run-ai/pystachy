# error: cannot send str to AsyncGenerator[int,None,None], whose send type is None: annotate its async generator function -> AsyncGenerator[T, S]
# asend() of a value other than None needs the send type of an AsyncGenerator[T, S] annotation, as
# a generator's send() needs Generator[Y, S, R]'s
async def ticks():
    yield 1


async def main() -> None:
    g = ticks()
    await g.asend(None)
    await g.asend("x")


main().send(None)
