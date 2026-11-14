# async with keeps its manager and flags apart from the program's variables, even ones named as
# its temporaries once were (__pys_aw<k>_*): the body's assignments neither skip nor repeat
# __aexit__(), and the variables keep their values through the statement


class CM:
    def __init__(self, name: str, suppress: bool) -> None:
        self.name = name
        self.suppress = suppress

    async def __aenter__(self) -> int:
        print("enter", self.name)
        return 1

    async def __aexit__(self, typ, exc, tb) -> bool:
        print("exit", self.name, typ is None)
        return self.suppress


async def flag() -> None:
    __pys_aw0_hit = True
    async with CM("a", False):
        print("inside", __pys_aw0_hit)
        __pys_aw0_hit = True
    print("after", __pys_aw0_hit)


async def raising() -> None:
    __pys_aw0_hit = False
    __pys_aw1_hit = False
    async with CM("outer", True):
        async with CM("inner", False):
            __pys_aw0_hit = True
            __pys_aw1_hit = True
            raise ValueError("boom")
    print("suppressed", __pys_aw0_hit, __pys_aw1_hit)


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass


run(flag())
run(raising())
