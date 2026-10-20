# A reference that is itself garbage when its referent dies never calls back, as in CPython: of
# references dropped before their referents, none calls back here either, but for a few that stale
# stack words may keep alive.
from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


calls: list[int] = [0]


def create() -> None:
    items = [Item(i) for i in range(256)]
    refs = [ref(item, lambda r: calls.append(calls.pop() + 1)) for item in items]
    assert all(r() is not None for r in refs)
    refs.clear()  # (CPython frees the references here, before the referents)


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


create()
churn()
ref(Item(-1))  # (making a reference runs the callbacks left)
print(calls[0] < 128)
