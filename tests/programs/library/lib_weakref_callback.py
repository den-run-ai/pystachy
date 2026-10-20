# A reference's callback runs with the reference once its referent has died, once, and never while
# the referent lives. CPython runs it when the referent's last reference goes; Pystachy after the
# collection that finds the referent dead, where a reference is next made or called (callbacks
# here allocate nothing, so no collection runs between those and the reads). Referents come in a
# cohort, so that a few that stale stack words keep alive cannot fail the test.
from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


calls: list[int] = [0] * 256
index: dict[ref[Item], int] = {}


def note(r: ref[Item]) -> None:
    calls[index[r]] += 1


def create() -> tuple[list[ref[Item]], list[Item]]:
    owners = [Item(i) for i in range(256)]
    refs = [ref(item, note) for item in owners]
    for i in range(256):
        index[refs[i]] = i
    return refs, owners


def churn() -> None:
    # (allocation that collects, without reading the references)
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def release(owners: list[Item]) -> None:
    owners.clear()


refs, owners = create()
plain = ref(owners[0], None)  # (None: no callback, as ref(owners[0]))
churn()
print(sum(calls), all(r() is not None for r in refs), plain() is owners[0])
release(owners)
churn()
dead = 0
for i, r in enumerate(refs):
    item = r()
    if item is None:
        dead += 1
        assert calls[i] == 1
    else:
        assert calls[i] == 0
        assert item.value == i
print(dead > 0)
