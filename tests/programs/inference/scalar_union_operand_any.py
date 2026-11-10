# pystachy: dynamic-any
# A conditional or boolean operand of a binary operator whose other operand is an Any value,
# where the result is wanted as int | str: the Any value's operator takes the union, so the
# operands are the unions they are anywhere else, also an or/and of an int and a str (an
# operand keeps a scalar for an operation on scalars: scalar_union_conditional_operand.py)
import sys
from typing import Any


def plus(a: int, b: int, c: bool, d: Any) -> int | str:
    return (a if c else b) + d


def or_plus(a: int, b: int, c: bool, d: Any) -> int | str:
    return ((a if c else b) or "x") + d


def arms_plus(a: int, c: bool, d: Any) -> int | str:
    return (a if c else "s") + d


def and_times(a: int, b: int, c: bool, d: Any) -> int | str:
    return ((a if c else b) and "ab") * d


def nested(a: int, b: int, c: bool, d: Any) -> int | str:
    return (((a if c else b) or (b if c else a)) or "y") + d


def any_left(a: int, b: int, c: bool, d: Any) -> int | str:
    return d * ((a if c else b) or 2)


def show(v: int | str) -> None:
    print(repr(v), type(v).__name__)


z = len(sys.argv) // 100  # (0, not a constant)
three: Any = 3 + z
text: Any = "y" * (z + 1)
show(plus(1, 2, True, three))
show(plus(1, 2, False, 40 + z))
show(or_plus(1, 2, True, three))
show(or_plus(z, 2, True, text))
show(arms_plus(5, True, three))
show(arms_plus(5, False, text))
show(and_times(1, 2, True, 2 + z))
show(and_times(z, 2, True, 2))
show(nested(z, 0, True, text))
show(nested(z, 4, True, 1))
show(any_left(z, 5, True, text))
show(any_left(4, z, True, three))
try:
    show(or_plus(z, 2, True, three))
except TypeError as e:
    print("TypeError", e)
