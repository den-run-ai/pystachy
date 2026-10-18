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
    owners = [Item(i) for i in range(256)]
    return [ref(item) for item in owners], owners


def observe_and_release(refs: list[ref[Item]], owners: list[Item]) -> None:
    # All references are first observed live. Even after this helper returns, AOT
    # inlining can leave a few target addresses in active registers or stack slots.
    print(all(r() is not None for r in refs))
    owners.clear()


refs, owners = create()
observe_and_release(refs, owners)
churn()
# Do not require a particular address to disappear from conservative roots; at
# least one observed-live reference must change, and no surviving value is stale.
print(any(r() is None for r in refs))
for i, r in enumerate(refs):
    value = r()
    if value is not None:
        assert value.value == i
