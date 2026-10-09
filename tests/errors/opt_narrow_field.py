# error: argument 1 of need() may be None (str | None), and a test does not narrow a global or a field (a call may change it): copy it to a local variable, and test that
class C:
    def __init__(self) -> None:
        self.s: str | None = "a"


def need(s: str) -> str:
    return s


def show(c: C) -> None:
    if c.s is not None:
        print(need(c.s))


show(C())
