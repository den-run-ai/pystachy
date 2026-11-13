# A test of a field narrows its reads until a call or a store may change it (it was a rejection).
class C:
    def __init__(self) -> None:
        self.s: str | None = "a"


def need(s: str) -> str:
    return s


def show(c: C) -> None:
    if c.s is not None:
        print(need(c.s))


show(C())
