def pys_foo(x: int) -> int: ...


def pys_bar(x: int) -> int:
    return pys_foo(x) + 1
