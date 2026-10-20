# The same where an item of a display raises: Pystachy evaluates only the item, as the display
# mixes types (tests/programs/imports/deftime_class_raises.py)
from typing import Iterable

NAMES = ["x"]


class Labels:
    data = {"a": 1, "b": "x", "c": NAMES[3]}
    xs: Iterable[int]
