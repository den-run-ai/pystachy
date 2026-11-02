# Objects and tuples that their functions read after collections hold their items until then, so
# weak references to those stay alive (docs/weakref.md: a live strong reference keeps the referent
# available), in cohorts of four: the optimizer deletes only objects that hold no reference
# (allocelide, lowering's alloc_call). Collections come from strs, which no optimization deletes
from _weakref import ref


class Item:
    def __init__(self, value: int) -> None:
        self.value = value


class Holder:
    def __init__(self, item: Item, tag: int) -> None:
        self.item = item
        self.tag = tag


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def holders() -> int:
    h0 = Holder(Item(0), 0)
    h1 = Holder(Item(1), 1)
    h2 = Holder(Item(2), 2)
    h3 = Holder(Item(3), 3)
    rs = [ref(h0.item), ref(h1.item), ref(h2.item), ref(h3.item)]
    churn()
    dead = len([r for r in rs if r() is None])
    return dead * 100 + h0.tag + h1.tag + h2.tag + h3.tag  # (the holders are read after the collections)


def tuples() -> int:
    t0 = (Item(0), 0)
    t1 = (Item(1), 1)
    t2 = (Item(2), 2)
    t3 = (Item(3), 3)
    rs = [ref(t0[0]), ref(t1[0]), ref(t2[0]), ref(t3[0])]
    churn()
    dead = len([r for r in rs if r() is None])
    return dead * 100 + t0[1] + t1[1] + t2[1] + t3[1]


print(holders(), tuples())
