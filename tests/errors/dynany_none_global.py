# error: 'g' holds None until it is given an Any value here; annotate it (g: Any = None)
# pystachy: dynamic-any
# A module variable that holds None until a function gives it an Any value: its None so far is a
# null pointer, not an Any value's box of None. Annotated (g: Any = None), it works: see
# tests/dynany_none_first.py.
from typing import Any


def get() -> Any:
    return "s"


g = None


def setg() -> None:
    global g
    g = get()


setg()
print(g)
