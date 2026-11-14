# gc.collect() runs a collection: objects that nothing refers to any more are found dead by it,
# where no allocation would have started one. The referents come in a cohort, so that a few that
# stale stack words keep alive cannot fail the test (lib_weakref_callback.py). CPython's reference
# counts free them as their list is cleared, and its collect() finds no more.
import gc
from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


def create() -> tuple[list[ref[Item]], list[Item]]:
    owners = [Item(i) for i in range(256)]
    refs = [ref(item) for item in owners]
    return refs, owners


def release(owners: list[Item]) -> None:
    owners.clear()


def dead(refs: list[ref[Item]]) -> int:
    n = 0
    for r in refs:
        if r() is None:
            n += 1
    return n


refs, owners = create()
gc.collect()
print(dead(refs), owners[255].value)
release(owners)
gc.disable()
gc.collect()
gc.enable()
print(dead(refs) > 0)
