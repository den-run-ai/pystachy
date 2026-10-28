# pystachy: dynamic-any
# A module that opts in to dynamic Any, in a program where another opts in to promoting ints
# (tests/programs/numbers/python_int_generics_dynamic.py): it reads an object of a generic class
# that the program specializes for ints as a dynamic value.
from typing import Any


def shown(s: Any) -> str:
    return f"{s.peek()} {s.top + 1} {type(s.top).__name__}"
