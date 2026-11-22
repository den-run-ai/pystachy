# collections.abc.Sequence and MutableSequence bases: iteration through __getitem__ until
# IndexError, in, reversed(), index() (with start and stop) and count(); append, extend, +=,
# insert, pop, remove, reverse and clear through the abstract methods. A Sequence is hashable
from collections.abc import MutableSequence, Sequence


class Evens(Sequence):
    def __init__(self, n: int) -> None:
        self.n = n

    def __getitem__(self, i: int) -> int:
        if i < 0:
            i += self.n
        if i < 0 or i >= self.n:
            raise IndexError("Evens index out of range")
        return 2 * i

    def __len__(self) -> int:
        return self.n


class Stack(MutableSequence):
    def __init__(self) -> None:
        self.items: list[str] = []

    def __getitem__(self, i: int) -> str:
        return self.items[i]

    def __setitem__(self, i: int, v: str) -> None:
        self.items[i] = v

    def __delitem__(self, i: int) -> None:
        del self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def insert(self, i: int, v: str) -> None:
        self.items.insert(i, v)


e = Evens(5)
print(list(e), 4 in e, 5 in e, e.index(6), e.count(2), list(reversed(e)), len(e), e[-1])
try:
    e.index(7)
except ValueError:
    print("ValueError index")
print(e.index(4, 1), e.index(8, -3), hash(e) == hash(e))
s = Stack()
s.append("a")
s.extend(["b", "c"])
s += ["d"]
s.insert(0, "z")
print(list(s), s.pop(), s.pop(0), list(s))
s.reverse()
print(list(s), s.index("b"))
s.remove("b")
print(list(s), len(s))
try:
    s.remove("q")
except ValueError:
    print("ValueError remove")
s.clear()
print(list(s), len(s))
