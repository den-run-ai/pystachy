# error: isinstance_tuple_unbound.py:7: error: local variable 'y' is read before its first assignment; declare it first (y: T)
# CPython reads every item of the tuple: y is not assigned yet (UnboundLocalError), although the test
# would stop at int


def f(n: int) -> bool:
    r = isinstance(n, (int, y))
    y = 5
    return r and y > 0


print(f(1))
