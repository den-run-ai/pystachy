# a, b = xs of a list reads its items once the length check has passed, for every item type,
# with a starred target too; a target whose setter or __setitem__ changes the list does not
# change what is unpacked, and a list of another length raises ValueError
class Box:
    def __init__(self, n: int) -> None:
        self.n = n


class Holder:
    def __init__(self, ys: list[int]) -> None:
        self.ys = ys
        self._f = 0

    @property
    def f(self) -> int:
        return self._f

    @f.setter
    def f(self, v: int) -> None:
        print("set f", v)
        self.ys.clear()
        self.ys.append(99)
        self._f = v


class Sink:
    def __init__(self, ys: list[int]) -> None:
        self.ys = ys

    def __setitem__(self, i: int, v: int) -> None:
        print("set", i, v)
        self.ys.pop()


def total(loops: int, xs: list[int]) -> int:
    a = b = c = 0
    for _ in range(loops):
        a, b, c = xs
        a, b, c = xs
    return a + b + c


print(total(3, [1, 2, 3]))
f1, f2 = [0.5, -2.25]
s1, s2, s3 = ["a", "", "c"]
t1, t2 = [True, False]
opts: list[int | None] = [None, 7]
o1, o2 = opts
mixed: list[int | str] = [1, "two"]
u1, u2 = mixed
n1, (n2, n3) = [[1], [2, 3]]
b1, b2 = [Box(4), Box(5)]
p1, p2 = [(1, "x"), (2, "y")]
print(f1, f2, s1, s2, s3, t1, t2, o1, o2, u1, u2, n1, n2, n3, b1.n + b2.n, p1, p2)
big = [i * 3 for i in range(6)]
g0, g1, g2, g3, g4, g5 = big
print(g0 + g1 + g2 + g3 + g4 + g5)
first, *mid, last = [1.5, 2.5, 3.5, 4.5]
print(first, mid, last)
*init, end = ["p", "q"]
print(init, end)
head, *rest = [[1, 2], [3]]
print(head, rest)
ys = [1, 2]
h = Holder(ys)
ys[0], h.f = ys
print(ys, h.f)
ys = [5, 6, 7]
k = Sink(ys)
k[0], k[1], k[2] = ys
print(ys)
ys = [8, 9, 10]
h = Holder(ys)
h.f, *zs = ys
print(ys, zs, h.f)
for bad in [[1, 2], [1, 2, 3, 4]]:
    try:
        a, b, c = bad
        print(a, b, c)
    except ValueError as e:
        print("ValueError:", e)
try:
    q1, *q2, q3 = [1]
except ValueError as e:
    print("ValueError:", e)
