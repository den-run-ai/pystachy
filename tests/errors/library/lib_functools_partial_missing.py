# error: add() missing 1 required positional argument: 'b'
# A partial's call is checked against its function's signature where it is compiled; CPython
# raises this TypeError when the call runs
from functools import partial


def add(a: int, b: int) -> int:
    return a + b


print(partial(add, 1)())
