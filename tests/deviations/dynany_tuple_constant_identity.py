# pystachy: dynamic-any
# A constant tuple with a boxed item is rebuilt at each return. CPython reuses
# the module's one tuple for both calls and for the ordinary display (#1016).
from typing import Any


class State:
    pass


def entry() -> tuple[State | None, Any]:
    return None, "ok"


plain = (None, "ok")
first = entry()
print(first == plain, first is entry(), first is plain)
