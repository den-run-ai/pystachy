# o[i, j], o[i, j] = v and o[i, j] op= v make the key tuple in the caller's frame where each
# __getitem__ and __setitem__ that the index may call (an override too) only reads the key: its
# items, its length or its type (Gen.stack_key). A method that keeps the key in any way, returns
# it, passes it on or lets a closure or a generator expression take it gets a heap tuple, as
# before: equal to the key, the same tuple wherever one call kept it, and one tuple for both calls
# of o[i, j] op= v. So does one that keeps it where isinstance() tests another value (an alias,
# which may hold one, or the key once assigned one), or through a len that is not the builtin.
# Str items of a key in the frame stay alive while __getitem__ allocates
from typing import Callable, Iterator

saved: list[tuple[int, int]] = []


def note(t: tuple[int, int]) -> None:
    saved.append(t)


class Grid:
    # reads its key's items only: no copy
    def __init__(self, rows: int, cols: int) -> None:
        self.cols = cols
        self.data: list[float] = [float(i) for i in range(rows * cols)]

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.data[key]
        if len(key) != 2:
            raise IndexError("two indices")
        i, j = key
        return self.data[i * self.cols + j]

    def __setitem__(self, key: tuple[int, int], v: float) -> None:
        p = 0
        for x in key:
            p = p * self.cols + x
        self.data[p] = v


class Keeper:
    # keeps its key in each way it can
    def __init__(self) -> None:
        self.last = (0, 0)
        self.order: list[tuple[int, int]] = []
        self.cells: dict[tuple[int, int], int] = {}
        self.seen: set[tuple[int, int]] = set()

    def __getitem__(self, key: tuple[int, int]) -> int:
        if key in self.cells:
            return self.cells[key]  # (a lookup keeps nothing)
        self.last = key
        self.order.append(key)
        self.order.append(key)  # (the copy the line before made)
        self.seen.add(key)
        note(key)
        k = key
        self.order.append(k)
        return len(self.order)

    def __setitem__(self, key: tuple[int, int], v: int) -> None:
        self.cells[key] = v


class Echo:
    def __getitem__(self, key):
        return key


class Both:
    def __init__(self) -> None:
        self.got: list[tuple[int, int]] = []
        self.put: list[tuple[int, int]] = []

    def __getitem__(self, key: tuple[int, int]) -> int:
        self.got.append(key)
        return key[0]

    def __setitem__(self, key: tuple[int, int], v: int) -> None:
        self.put.append(key)


class Missing(Exception):
    def __init__(self, key: tuple[int, int]) -> None:
        super().__init__("missing")
        self.key = key


class Raises:
    def __getitem__(self, key: tuple[int, int]) -> int:
        if key[0] < -2:
            raise KeyError(key)
        if key[0] < 0:
            raise Missing(key)
        return key[0] + key[1]


class Closure:
    def __getitem__(self, key):
        def show() -> str:
            return f"{key}"

        return show


class Loops:
    def __getitem__(self, key: tuple[int, int]) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        while len(out) < 2 and key[0] >= 0:  # (the test runs again after the body)
            out.append(key)
        return out


class Base:
    def __getitem__(self, key: tuple[int, int]) -> str:
        return str(key[0] * 10 + key[1])


class Kept(Base):
    def __init__(self) -> None:
        self.keys: list[tuple[int, int]] = []

    def __getitem__(self, key: tuple[int, int]) -> str:
        self.keys.append(key)
        return "kept"


class Captured(Base):
    def __getitem__(self, key: tuple[int, int]) -> str:
        def first() -> str:
            return f"{key}!"

        return first()


class Named:
    # str items: the frame's tuple holds the only references to them while __getitem__ allocates
    def __getitem__(self, key: tuple[str, str]) -> str:
        joined = key[0] + "+" + key[1]
        return joined + "|" + key[1] + key[0]


class Aliased:
    # isinstance(x, int) is true where x is not the key: the block keeps it
    def __init__(self) -> None:
        self.keys: list[tuple[int, int]] = []

    def __setitem__(self, key: tuple[int, int], value: object) -> None:
        if isinstance(value, int):
            self.keys.append(key)
        else:
            value = key  # (value: an alias of key, which holds another value above)

    def __getitem__(self, key):
        k = key
        key = 5
        if isinstance(key, int):
            self.keys.append(k)
        return 0


measured: list[tuple[int, int]] = []


def measure(t: tuple[int, int]) -> int:
    measured.append(t)
    return 2


measures: list[Callable[[tuple[int, int]], int]] = [measure]


class Measured:
    def __getitem__(self, key: tuple[int, int]) -> int:
        return [len(key) for len in measures][0] + key[0]  # (len: the comprehension's measure)


class Lazy:
    def __getitem__(self, key: tuple[int, int]) -> Iterator[int]:
        return (key[n] * 100 for n in range(2))  # (it reads the key as it is iterated)


class Shape:
    def __getitem__(self, key: tuple[int, int]) -> int:
        return key[0] * key[1]


class Square(Shape):
    def __getitem__(self, key: tuple[int, int]) -> int:
        i, j = key
        return i * i + j * j


g = Grid(3, 4)
total = 0.0
for i in range(3):
    for j in range(4):
        g[i, j] = float(i * j) + 0.5
        g[i, j] += 1.0
        total += g[i, j]
print(total, g[2, 3], g[(1, 1)], g[5])
try:
    print(g[1, 2, 3])
except IndexError as e:
    print("IndexError", e)

kp = Keeper()
got = [kp[i, i + 1] for i in range(3)]
print(got, kp.last, kp.order, sorted(kp.seen), saved)
print(kp.order[0] is kp.order[1], kp.order[1] is kp.order[2], kp.order[2] is kp.order[3], saved[1] is kp.order[3], kp.last is kp.order[6])
kp[5, 6] = 1
kp[7, 8] = 2
kp[5, 6] += 10
kp[1, 1] += 100
print(kp.cells, kp[5, 6], kp.order[-1], sorted(kp.cells)[0] == (1, 1))
e = Echo()
echoed = [e[i, i * i] for i in range(4)]
print(echoed, echoed[1] is echoed[2], e[3])
b = Both()
for i in range(2):
    b[i, 9] += 1
b[4, 4] = b[3, 3]
print(b.got, b.put, b.got[0] is b.put[0], b.got[1] is b.put[1], b.got[0] is b.got[1])

r = Raises()
print(r[2, 3])
caught: list[tuple[int, int]] = []
for i in range(4):
    try:
        print(r[-i - 1, i])
    except Missing as e:
        caught.append(e.key)
    except KeyError as e:
        print("KeyError", e)
print("caught", caught, r[4, 4])

fs = [Closure()[i, -i] for i in range(3)]
print([f() for f in fs])
print(Loops()[3, 4], Loops()[-1, 0])

kept = Kept()
objs: list[Base] = [Base(), kept, Captured()]
labels = [o[n, n + 1] for o in objs for n in range(2)]
print(labels, kept.keys)

nm = Named()
print([nm[str(i) * 4, "y" * i] for i in range(5)])
shapes: list[Shape] = [Shape(), Square()]
print([s[n, n + 1] for s in shapes for n in range(3)])
al = Aliased()
for i in range(3):
    al[i, i + 1] = i
print([al[i, -i] for i in range(3)], al.keys)
print([Measured()[i, i + 1] for i in range(3)], measured)
lazies = [Lazy()[i, i + 1] for i in range(3)]
print([list(x) for x in lazies])
