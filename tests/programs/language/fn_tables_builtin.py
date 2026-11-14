# A builtin function in a table beside a function with an annotated signature: the Callable
# of that signature, which the builtin is called as. Also in a module that compiles Any
# dynamically, where no Any value holds a builtin function.
import math


def add(a: int, b: int) -> int:
    return a + b


def half(x: float) -> int:
    return int(x / 2)


MIXED = {"add": add, "max": max}
PAIR = [add, min]
ROUND = [half, math.floor]
print(sorted((k, f(2, 5)) for k, f in MIXED.items()), [f(7, 3) for f in PAIR], [f(9.5) for f in ROUND])
pick = add if len(MIXED) > 5 else max
print(pick(4, 9))
