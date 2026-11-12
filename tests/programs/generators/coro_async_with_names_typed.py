# async with's manager and value are no variables of the program, even of one named as its
# temporaries once were (__pys_aw<k>_*): their types are independent (here str and int)


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


async def manager_and_value() -> None:
    __pys_aw0_mgr = "mine"
    __pys_aw0_val = 10
    async with CM("b", False) as v:
        print("inside", v, __pys_aw0_mgr, __pys_aw0_val)
        __pys_aw0_val = 20
        __pys_aw0_mgr = "changed"
    print("after", __pys_aw0_mgr, __pys_aw0_val)


def run(c) -> None:
    try:
        c.send(None)
    except StopIteration:
        pass


run(manager_and_value())
