# an exception raised in compiled code that the runtime called back (a comparison during sort(),
# sorted(), min(), ==, a __repr__ inside a list's repr) passes through the runtime's frames to
# the handler; the list being sorted has all its items again


class Item:
    def __init__(self, v: int):
        self.v = v

    def __lt__(self, other: "Item") -> bool:
        if self.v == 13 or other.v == 13:
            raise ValueError(f"cannot compare {self.v} and {other.v}")
        return self.v < other.v

    def __eq__(self, other: "Item") -> bool:
        if self.v < 0:
            raise TypeError("negative")
        return self.v == other.v

    def __repr__(self) -> str:
        if self.v == 7:
            raise RuntimeError("no repr for 7")
        return f"Item({self.v})"


items = [Item(5), Item(3), Item(13), Item(1), Item(8)]
try:
    items.sort()
except ValueError as e:
    print("sort:", e)
print(len(items), sorted([it.v for it in items]))
try:
    print(sorted(items))
except ValueError as e:
    print("sorted:", e)
try:
    print(min(items))
except ValueError as e:
    print("min:", e)
try:
    print(Item(-1) in items)
except TypeError as e:
    print("in:", e)
try:
    print([Item(1), Item(7)])
except RuntimeError as e:
    print("repr:", e)
print([Item(1), Item(2)])
good = [Item(4), Item(2), Item(9)]
good.sort()
print(good)
