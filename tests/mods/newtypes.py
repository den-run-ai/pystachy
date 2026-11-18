# A NewType that another module imports (tests/programs/generics/newtype.py)
from typing import NewType

Meters = NewType("Meters", int)


def double(m: Meters) -> Meters:
    return Meters(m * 2)
