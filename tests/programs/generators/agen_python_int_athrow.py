# pystachy: python-int
# athrow() of an async generator of ints, in a module that opts in to promoting ints: its value is
# an int | None, what the async generator yields where it handles the exception (past 64 bits too),
# or None where it has already finished, as in CPython. Such a module did not compile ("expected
# int, got None") while athrow() of a promoting int gave a promoting int, which None is not.


async def counter():
    n = 2**62
    while True:
        try:
            yield n
        except ValueError:
            n = n * 8


async def main() -> None:
    g = counter()
    print(await g.__anext__())
    print(await g.athrow(ValueError))
    v = await g.athrow(ValueError("again"))
    print(v, v is None)
    if v is not None:
        print("past 64 bits:", v > 2**64)
    try:
        await g.athrow(KeyError)
    except KeyError:
        print("KeyError leaves it")
    w = await g.athrow(ValueError)
    print(w, w is None)


c = main()
try:
    c.send(None)
except StopIteration:
    print("done")
