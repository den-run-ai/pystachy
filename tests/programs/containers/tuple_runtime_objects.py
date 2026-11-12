# tuple[C, ...] holds objects of the program's classes: built by tuple(), displays and
# concatenation, read by index, slice, iteration and unpacking, shown with their __repr__
class Item:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Item({self.n})"

    def __bool__(self) -> bool:
        return self.n != 0

    def __lt__(self, other: "Item") -> bool:
        return self.n < other.n


class Base:
    def kind(self) -> str:
        return "base"


class Derived(Base):
    def kind(self) -> str:
        return "derived"


def items(ns: list[int]) -> tuple[Item, ...]:
    return tuple(Item(n) for n in ns)


def kinds(xs: tuple[Base, ...]) -> list[str]:
    return [x.kind() for x in xs]


t = items([3, 0, 2])
one = items([7])
empty: tuple[Item, ...] = ()
print(t, repr(one), str(empty), f"{one!r}", len(t), bool(t), bool(empty))
print(t[0], t[-1], t[1:], t[::-1], t[5:])
for i, item in enumerate(t):
    print(i, item.n)
for a, b in zip(t, list(reversed(t))):
    print(a, b)
first, *rest = t
x, y, z = t
print(first, rest, x, y, z)
print(list(t), sorted(t), min(t), max(t, key=lambda i: i.n))
print(any(t), all(t), list(filter(None, t)), [i.n * 2 for i in t])
print(t + one, t + () is t, () + t is t, t[:] is t, tuple(t) is t)
display: tuple[Item, ...] = (Item(4), Item(5))
print(display + (Item(6),), (Item(1),) + display)
print(t.index(t[2]), t.index(t[2], 1), t.count(t[0]))
try:
    print(t[3])
except IndexError as e:
    print("IndexError:", e)
try:
    print(t.index(Item(9)))
except ValueError as e:
    print("ValueError:", e)
print(len(set(t)), len(frozenset(t + t)))
maybe: tuple[Base, ...] = (Base(), None, Derived())
print([b is None for b in maybe])
derived: tuple[Derived, ...] = (Derived(), Derived())
base: tuple[Base, ...] = derived
print(base is derived, kinds(base), kinds(derived), kinds(base + (Base(),)))
print(" ".join(str(i) for i in t))
