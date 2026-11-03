# Objects that their function reads after collections hold their fields' objects until then, so
# weak references to those stay alive (docs/weakref.md: a live strong reference keeps the referent
# available). The optimizer could forward the fields across the collections and leave the holders'
# addresses dead: it deletes only objects that hold no reference (allocelide, lowering's
# alloc_call). Collections come from strs, which no optimization deletes
from _weakref import ref


class Item:
    def __init__(self, value: int) -> None:
        self.value = value


class Holder:
    def __init__(self, item: Item, tag: str) -> None:
        self.item = item
        self.tag = tag


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def run() -> None:
    ha = Holder(Item(1), "a")
    hb = Holder(Item(2), "b")
    hc = Holder(Item(3), "c")
    hd = Holder(Item(4), "d")
    rs = [ref(ha.item), ref(hb.item), ref(hc.item), ref(hd.item)]
    churn()
    # (each holder is read below: in CPython each still holds its item here)
    print("dead while their holders live:", len([r for r in rs if r() is None]))
    print(ha.tag + hb.tag + hc.tag + hd.tag)


run()
