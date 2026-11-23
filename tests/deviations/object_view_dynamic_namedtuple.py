# pystachy: dynamic-any
# Documented deviation: a NamedTuple's object that an Any value holds passes isinstance(x, tuple),
# but is no sequence through the Any value (docs/dynamic-any.md#deviations), nor through a value of
# object that holds the Any value and a tuple test narrowed to a view: len() raises TypeError. CPython
# prints "2 5". (A NamedTuple's object stored as object itself is a sequence through its view:
# tests/programs/classes/object_views_classes.py.)
from typing import Any, NamedTuple


class N(NamedTuple):
    x: int
    y: str


def main() -> None:
    a: Any = N(5, "five")
    o: object = a
    print(isinstance(o, tuple), isinstance(o, N), o)
    if isinstance(o, tuple):
        print(len(o), o[0])


main()
