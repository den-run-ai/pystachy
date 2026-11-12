# async for keeps its iterator and flags apart from the program's variables, even ones named as
# its temporaries once were (__pys_aw<k>_*): assigning them in the body neither ends nor restarts
# a loop, and break, continue and else behave as in CPython


class Ticks:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __aiter__(self) -> "Ticks":
        return self

    async def __anext__(self) -> int:
        if self.i >= self.n:
            raise StopAsyncIteration
        self.i += 1
        return self.i


async def control() -> None:
    __pys_aw0_run = True
    __pys_aw1_run = True
    async for x in Ticks(4):
        __pys_aw0_run = False
        if x == 2:
            continue
        async for y in Ticks(3):
            __pys_aw1_run = False
            if y == 2:
                break
            print("pair", x, y)
        else:
            print("inner else")
        if x == 3:
            break
    else:
        print("outer else")
    print("after", __pys_aw0_run, __pys_aw1_run)


async def exhausted() -> None:
    __pys_aw0_run = True
    async for x in Ticks(2):
        print("item", x)
        __pys_aw0_run = False
    else:
        print("else", __pys_aw0_run)


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass


run(control())
run(exhausted())
