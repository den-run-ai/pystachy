# async def and await (PEP 492): a call makes a coroutine object and runs none of its body; await
# runs an awaitable to its return and gives what it returns; send(None) runs a coroutine until it
# suspends or returns (StopIteration). Recursive coroutines and values of several types.
import types


@types.coroutine
def pause(tag: str):
    yield tag


async def square(x: int) -> int:
    return x * x


async def label(name: str, n: int) -> str:
    await pause("label " + name)
    return name + "=" + str(n)


async def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return await fibonacci(n - 1) + await fibonacci(n - 2)


async def nothing() -> None:
    print("nothing ran")


async def total(xs: list[int]) -> float:
    t = 0
    for x in xs:
        t += await square(x)
    await nothing()
    return t / 2


async def main() -> list[str]:
    print("main starts")
    a = await square(7)
    b = await label("b", a)
    c = await fibonacci(15)
    d = await total([1, 2, 3])
    print(a, b, c, d)
    out = [b]
    for i in range(3):
        out.append(await label(str(i), i * 10))
    return out


def run(c) -> int:
    # a minimal driver: send None until the coroutine returns, printing what it yields
    steps = 0
    try:
        while True:
            print("yielded", c.send(None))
            steps += 1
    except StopIteration:
        print("returned after", steps, "steps")
    return steps


m = main()
print("created")
run(m)
f = fibonacci(20)
run(f)
print(type(m).__name__)
