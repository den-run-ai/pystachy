# error: object_sentinel_enclosing_param.py:11: error: expected int, got object
# CPython prints False: f's default reads outer's parameter S, another object(), not the sentinel
S = object()


def g(x: int = S) -> bool:
    return True if x is S else False


def outer(S: object) -> bool:
    def f(x: int = S) -> bool:
        return g(x)
    return f()


print(outer(object()))
