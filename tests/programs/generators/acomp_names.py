# An asynchronous comprehension keeps apart from the program's names: the variables of the async
# generator that steps through an iterator object for it, and the comprehension's own target, which
# the code around it does not see; a name bound by := in it is the function's.
class Pairs:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0

    def __aiter__(self) -> "Pairs":
        return self

    async def __anext__(self) -> int:
        if self.i >= self.n:
            raise StopAsyncIteration
        self.i += 1
        return self.i


async def main() -> None:
    run = "outer run"
    val = -1
    x = "outer x"
    __pys_ac_run = False
    print([val * x async for x in Pairs(3)])
    print(run, val, x, __pys_ac_run)
    print([(last := x) async for x in Pairs(2)], last)
    print({run: x async for x in Pairs(1)})


c = main()
try:
    c.send(None)
except StopIteration:
    print("done")
