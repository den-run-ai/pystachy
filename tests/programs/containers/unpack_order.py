# Unpacking takes every item of a list (or of what an object's __iter__ steps through) before
# it stores the first, so a target that changes the list does not change what is unpacked
from typing import Iterator


class C:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)

    def __setitem__(self, i: int, v: int) -> None:
        self.xs[i] = v


class S:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __setitem__(self, i: int, v: int) -> None:
        print("set", i, v)
        self.xs.clear()


def get(xs: list[int]) -> list[int]:
    return xs


xs = [1, 2]
xs[1], xs[0] = xs
print(xs)
c = C()
c.xs[1], c.xs[0] = c
print(c.xs)
c = C()
c[1], c[0] = c
print(c.xs)
ys = [1, 2]
s = S(ys)
s[0], s[1] = ys
print(ys)
xs = [1, 2]
xs[1], xs[0] = get(xs)
print(xs)
zs = [3, 4, 5]
(zs[2], zs[1]), zs[0] = [zs[0], zs[1]], 9
print(zs)
ws = [[1, 2], [3, 4]]
for ws[1][0], ws[1][1] in ws:
    print(ws)
a, b = xs
print(a, b)
