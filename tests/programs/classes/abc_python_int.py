# pystachy: python-int
# collections.abc's Sequence and the views of a Mapping in a module of promoting ints: index()
# and the views' in test identity and then equality (x is y or x == y) of ints past 64 bits.
# Sequence's in and count() read the items through lib's 64-bit generator, a fixed-width read
# (docs/python-int.md)
from collections.abc import Mapping, Sequence


class Powers(Sequence):
    def __init__(self, n: int) -> None:
        self.n = n

    def __getitem__(self, i: int) -> int:
        if i < 0 or i >= self.n:
            raise IndexError(i)
        return 2 ** (32 * i)

    def __len__(self) -> int:
        return self.n


class Sizes(Mapping):
    def __init__(self) -> None:
        self.d = {"small": 7, "huge": 3 ** 50}

    def __getitem__(self, k: str) -> int:
        return self.d[k]

    def __iter__(self):
        return iter(self.d)

    def __len__(self) -> int:
        return len(self.d)


p = Powers(4)
print(p.index(2 ** 32), p.index(2 ** 96), list(p)[-1])
try:
    p.index(5)
except ValueError:
    print("ValueError")
s = Sizes()
print(("huge", 3 ** 50) in s.items(), ("huge", 7) in s.items(), ("small", 7) in s.items())
print(3 ** 50 in s.values(), 3 ** 50 + 1 in s.values(), 7 in s.values(), 8 in s.values())
