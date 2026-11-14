# Async defs that never suspend (each await is of a call of such an async def by its name) run
# without a coroutine where they are awaited by name: the result, the exceptions, the order of
# effects and PEP 479 are what CPython's coroutines give. Others still suspend: an await of
# something that yields, through any chain of calls, reaches the code that runs the coroutine.
import types


@types.coroutine
def pause(tag: str):
    yield tag


async def add(a: int, b: int = 10, *, scale: int = 1) -> int:
    print("add", a, b, scale)
    return (a + b) * scale


async def fib(n: int) -> int:
    if n <= 1:
        return n
    return await fib(n - 1) + await fib(n - 2)


async def stop() -> int:
    raise StopIteration


async def middle() -> str:
    try:
        await stop()
    except StopIteration:
        return "caught StopIteration"
    except RuntimeError as e:
        return "caught RuntimeError: " + str(e)
    return "nothing"


async def raises(n: int) -> int:
    if n == 0:
        raise ValueError("bottom")
    return await raises(n - 1) + 1


async def even(n: int) -> bool:
    if n == 0:
        return True
    return await odd(n - 1)


async def odd(n: int) -> bool:
    if n == 0:
        await pause("odd bottom")
        return False
    return await even(n - 1)


async def shadow(add) -> int:
    return await add(1)


async def one(x: int) -> int:
    return x + 1


async def main() -> None:
    print(await add(1), await add(2, 3), await add(b=1, a=2, scale=3))
    print(await fib(20))
    print(await middle())
    try:
        await raises(3)
    except ValueError as e:
        print("raised", e)
    print(await even(4))
    print(await even(3))
    print(await shadow(one))
    c = fib(10)
    print("stored", await c)


def run(c) -> None:
    try:
        while True:
            print("yielded", c.send(None))
    except StopIteration:
        print("returned")


run(main())
run(fib(12))
