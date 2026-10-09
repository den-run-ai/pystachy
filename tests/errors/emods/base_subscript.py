class Plain:
    pass


class Sub(Plain[int]):
    "CPython raises TypeError when the class statement runs"


def g() -> int:
    return 22
