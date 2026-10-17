from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


def churn() -> None:
    # Do not dereference the weak reference while allocating: that would introduce
    # fresh strong references whose conservative lifetime could obscure this test.
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def create():
    owners = [Item(7)]
    return ref(owners[0]), owners


def observe_and_release(r: ref[Item], owners: list[Item]) -> None:
    # Return this frame before collecting: stale bits from the first dereference
    # in an active frame can legitimately retain a target in a conservative GC.
    print(r() is not None)
    owners.clear()


r, owners = create()
observe_and_release(r, owners)
churn()
print(r() is None)
