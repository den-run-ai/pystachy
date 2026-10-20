# The callbacks of a referent's references run newest reference first, as CPython runs them, and a
# callback may make and call references while it runs.
from typing import Callable
from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


when: list[int] = [-1] * 128  # (the tick of each reference's callback: two per item)
tick: list[int] = [0]
spare = Item(-1)


def noter(k: int) -> Callable[[ref[Item]], None]:
    def note(r: ref[Item]) -> None:
        when[k] = tick[0]
        tick[0] += 1
        assert r() is None
        assert ref(spare)() is spare  # (a reference made and called in a callback)
    return note


def create() -> tuple[list[ref[Item]], list[Item]]:
    owners = [Item(i) for i in range(64)]
    refs: list[ref[Item]] = []
    for i in range(64):
        refs.append(ref(owners[i], noter(2 * i)))
        refs.append(ref(owners[i], noter(2 * i + 1)))
    return refs, owners


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


refs, owners = create()
owners.clear()
churn()
# (the live referents, held while the callbacks, which allocate, run, so that every reference that
# reads None here has called back)
pairs = [(refs[2 * i](), refs[2 * i + 1]()) for i in range(64)]
both = 0
for i in range(64):
    a, b = pairs[i]
    if a is None and b is None:
        both += 1
        assert 0 <= when[2 * i + 1] < when[2 * i]
    else:
        assert a is not None and b is a
        assert when[2 * i] == -1 and when[2 * i + 1] == -1
print(both > 0, tick[0] == 2 * both)
