from _weakref import ReferenceType, ref


class Item:
    def __init__(self, value: int):
        self.value = value


def make(obj: Item) -> ReferenceType[Item]:
    return ref(obj)


def identity(obj: Item) -> None:
    r = ref(obj)
    s = ReferenceType(obj)
    print(r() is obj, s() is obj)
    typed: ReferenceType[Item] = make(obj)
    assert typed() is obj
    live = r()
    if live is not None:
        print(live.value)
    obj.value = 42
    print(r().value)
    # Allocations between reads exercise a live referent and the separate wrapper/handle
    # rooting under PYSTACHY_GC_STRESS=1 as well as ordinary execution.
    for i in range(100):
        xs = [Item(i), Item(i + 1)]
        assert xs[0].value == i
        assert r() is obj
    print("live referent survives")


identity(Item(7))
