class C:
    def __init__(self, v: int) -> None:
        self.v = v


def f(x: C[int]) -> int:
    return 0


def g() -> int:
    return 21
