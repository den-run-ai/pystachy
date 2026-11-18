# error: object_sentinel_enclosing_cell.py:12: error: expected int, got object
# CPython prints False: f's default reads outer's parameter S through mid, not the sentinel
S = object()


def g(x: int = S) -> bool:
    return True if x is S else False


def outer(S: object) -> bool:
    def mid() -> bool:
        def f(x: int = S) -> bool:
            return g(x)
        return f()
    return mid()


print(outer(object()))
