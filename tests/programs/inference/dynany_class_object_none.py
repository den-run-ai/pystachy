# pystachy: dynamic-any
# NoneType's class object, which type(x) gives of an x that is None, goes through Any and
# back into its typed location.
from typing import Any


class C:
    pass


def trip(x: C | None) -> None:
    k = type(x)
    a: Any = k
    back: type[C] = a
    print(back.__name__, back is k)


trip(C())
trip(None)
