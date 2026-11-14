# async for's iterator, flag and value are no variables of the program, even of ones named as its
# temporaries once were (__pys_aw<k>_*): their types are independent (here int and str)


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


async def flags() -> None:
    __pys_aw0_run = 0
    __pys_aw0_it = "mine"
    __pys_aw0_val = -1
    async for x in Ticks(3):
        __pys_aw0_run = __pys_aw0_run + x
        __pys_aw0_it = "changed"
        __pys_aw0_val = x * 10
        print("item", x, __pys_aw0_run, __pys_aw0_val)
    else:
        print("else", __pys_aw0_run, __pys_aw0_it, __pys_aw0_val)


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass


run(flags())
