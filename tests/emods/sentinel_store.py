S = object()


def f(x: int = S) -> bool:
    return True if x is S else False
