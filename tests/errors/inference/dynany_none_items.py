# error: 'xs' holds None items until it is given an Any value here; annotate it (xs: list[Any] = ...)
# pystachy: dynamic-any
# A list of None items, typed by its first fill, that an Any value fills: its None items are null
# pointers, not an Any value's boxes of None. Annotated (xs: list[Any] = [None] * 3), it works:
# see tests/programs/inference/dynany_none_first.py.
from typing import Any


def get() -> Any:
    return "s"


xs = [None] * 3
xs[0] = get()
print(xs)
