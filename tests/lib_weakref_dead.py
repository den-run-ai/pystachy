from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


def create():
    # A conservative collector can retain individual stale stack/register words,
    # particularly when AOT inlines this helper. A cohort still requires real
    # weak ownership: making every handle a strong edge would retain all targets.
    return [ref(Item(i)) for i in range(256)]


def churn() -> None:
    # Force collections without polling the reference: a successful dereference would
    # itself introduce a fresh conservative strong root. Allocation pressure is bounded.
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


refs = create()
churn()
print(any(r() is None for r in refs))
for i, r in enumerate(refs):
    value = r()
    if value is not None:
        assert value.value == i
