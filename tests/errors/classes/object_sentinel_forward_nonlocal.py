# error: object_sentinel_forward_nonlocal.py:16: error: expected int, got object
# CPython prints False: replace() gives x another object(), which g's x is S tests
S = object()


def g(x: int = S) -> bool:
    return True if x is S else False


def f(x: int = S) -> bool:
    def replace() -> None:
        nonlocal x
        x = object()

    replace()
    return g(x)


print(f())
