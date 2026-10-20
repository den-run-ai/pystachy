# error: field 'v' of C holds None until it is given an Any value here; annotate it (self.v: Any = None)
# pystachy: dynamic-any
# A field that __init__ sets to None, and that a function other than the class's methods gives
# an Any value: until then its None is a null pointer, which `c.v is None` compiled so far tests,
# not an Any value's box of None. Annotated (self.v: Any = None), it works: see
# tests/programs/inference/dynany_none_first.py.
from typing import Any


def get(i: int) -> Any:
    return [1, "s"][i]


class C:
    def __init__(self) -> None:
        self.v = None


c = C()
print(c.v is None)


def later(x, i):
    x.v = get(i)


later(c, 1)
print(c.v)
