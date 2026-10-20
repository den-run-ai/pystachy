# error: argument 1 of f() may be None (int | None); test it with 'is not None' first
def f(n: int) -> int:
    return n + 1


def g(x: int | None) -> int:
    return f(x)
