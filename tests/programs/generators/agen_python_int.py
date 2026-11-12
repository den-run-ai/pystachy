# pystachy: python-int
# In a module that opts in to promoting ints, an async generator yields ints past 64 bits to its
# consumer, and its awaits pass such ints on to the code that runs the coroutine that consumes it
# (an int's two words, in its own yields and in an await's suspension); an asynchronous
# comprehension takes them too.
import types


@types.coroutine
def tick(v: int):
    yield v


async def powers(n: int):
    x = 1
    for i in range(n):
        await tick(x * 3)
        yield x
        x = x * 2 ** 40


async def main() -> None:
    async for v in powers(4):
        print(v)
    print([v async for v in powers(3)])


c = main()
try:
    while True:
        print("driver", c.send(None))
except StopIteration:
    print("done")
