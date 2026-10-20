# error: 'last' is assigned None and then an Any value, which it cannot hold here; annotate it (last: Any = None)
# pystachy: dynamic-any
# A generator's local is not made dynamic from its first store as other functions' locals are
# (its frame is laid out once), so its None would stay a null pointer that the Any value's
# storage reads. Annotated (last: Any = None), it works: see tests/dynany_none_first.py.
from typing import Any


def get(i: int) -> Any:
    return [1, "s"][i]


def gen(n: int):
    last = None
    for i in range(n):
        last = get(i)
        yield last
    yield last


print(list(gen(0)))
