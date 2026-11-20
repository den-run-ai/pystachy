# The membership tests of collections.abc's Sequence, ValuesView and ItemsView (in, index() and
# count()) test identity before equality, as CPython's do: an object whose __eq__ is never true
# is found where the very object is, without a call of its __eq__. Numbers compare by value
from collections.abc import Mapping, Sequence


class Never:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> bool:
        print("__eq__", self.name)
        return False


class Row(Sequence):
    def __init__(self, items: list[Never]) -> None:
        self.items = items

    def __getitem__(self, i: int) -> Never:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)


class Floats(Sequence):
    def __init__(self, items: list[float]) -> None:
        self.items = items

    def __getitem__(self, i: int) -> float:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)


class Prices(Mapping):
    def __init__(self) -> None:
        self.d = {"tea": 3, "jam": 5}

    def __getitem__(self, k: str) -> int:
        return self.d[k]

    def __iter__(self):
        return iter(self.d)

    def __len__(self) -> int:
        return len(self.d)


a = Never("a")
b = Never("b")
r = Row([a, b])
print(b in r, r.index(b), r.count(a))
print(Never("c") in r)
f = Floats([0.5, 1.5, 0.5])
print(1.5 in f, 2.5 in f, f.index(0.5, 1), f.count(0.5), f.count(2))
p = Prices()
print(("tea", 3) in p.items(), ("tea", 4) in p.items(), ("tea", 3.0) in p.items(), ("x", 3) in p.items())
print(5 in p.values(), 6 in p.values(), 5.0 in p.values(), True in p.values())
