from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


def create():
    return ref(Item(7))


def churn() -> None:
    # Force collections without polling the reference: a successful dereference would
    # itself introduce a fresh conservative strong root. Allocation pressure is bounded.
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


r = create()
churn()
print(r() is None)
