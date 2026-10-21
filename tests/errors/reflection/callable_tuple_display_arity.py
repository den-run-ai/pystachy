# error: callable_tuple_display_arity.py:12: error: a() takes 0 positional arguments but 1 was given (making a Callable[[int], int] of <function a>
# A function in a tuple display becomes the Callable expected there only where it takes the
# Callable's arguments (#245), as in a list display or an annotated variable.
from typing import Callable


def a() -> None:
    print("a")


ops: list[tuple[str, Callable[[int], int]]] = []
ops.append(("a", a))
print(len(ops))
