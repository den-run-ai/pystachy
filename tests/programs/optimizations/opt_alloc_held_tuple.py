# A tuple that its function reads after collections holds its item until then, so a weak reference
# to the item stays alive (docs/weakref.md: a live strong reference keeps the referent available).
# The optimizer could forward the tuple's slots across the collections and leave the tuple's
# address dead: it deletes only objects that hold no reference (allocelide, lowering's
# alloc_call). Collections come from strs, which no optimization deletes
from _weakref import ref


class Item:
    def __init__(self, value: int) -> None:
        self.value = value


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def run(n: int) -> None:
    t = (Item(n), n * 2)  # (CPython's t holds the item until run returns)
    r = ref(t[0])
    churn()
    print("referent of a live tuple collected:", r() is None, t[1])


run(1)
