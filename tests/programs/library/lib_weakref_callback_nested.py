# A callback that calls or makes a reference runs to its end before the referent's next callback
# starts, as in CPython, which calls a referent's callbacks one after another.
from typing import Callable
from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


log: list[list[str]] = [[] for _ in range(64)]
spare = Item(-1)


def noter(k: int, name: str) -> Callable[[ref[Item]], None]:
    def note(r: ref[Item]) -> None:
        log[k].append("begin " + name)
        assert r() is None  # (a reference called in a callback)
        assert ref(spare)() is spare  # (and one made)
        log[k].append("end " + name)
    return note


def create() -> tuple[list[ref[Item]], list[Item]]:
    owners = [Item(i) for i in range(64)]
    refs: list[ref[Item]] = []
    for i in range(64):
        refs.append(ref(owners[i], noter(i, "old")))
        refs.append(ref(owners[i], noter(i, "new")))
    return refs, owners


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


refs, owners = create()
owners.clear()
churn()
# (the live referents, held while the callbacks run, so that every reference that reads None here
# has called back)
pairs = [(refs[2 * i](), refs[2 * i + 1]()) for i in range(64)]
both = 0
for i in range(64):
    a, b = pairs[i]
    if a is None and b is None:
        both += 1
        assert log[i] == ["begin new", "end new", "begin old", "end old"]
    else:
        assert a is not None and b is a and log[i] == []
print(both > 0)
