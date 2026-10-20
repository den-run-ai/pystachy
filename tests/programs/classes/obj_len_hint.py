# list(), sorted() and list.extend() of an object call its __len__ as a length hint once __iter__
# has run, as CPython's do; the other consumers do not
from typing import Iterator


class C:
    def __init__(self) -> None:
        self.xs = ["b", "a"]

    def __iter__(self) -> Iterator[str]:
        print("iter")
        return iter(self.xs)

    def __len__(self) -> int:
        print("len")
        self.xs.append("c")
        return 1


c = C()
print("join", "".join(c))
print("list", list(c))
print("sorted", sorted(c))
ys: list[str] = []
ys.extend(c)
print("extend", ys)
zs = []
zs.extend(c)
print("extend", zs)
print("min", min(c), "max", max(c))
a, b, d, e, f, g = c
print("unpack", a)
print("enumerate", list(enumerate(c)))
print("in", "a" in c)
for x in c:
    pass
print([x for x in c])
