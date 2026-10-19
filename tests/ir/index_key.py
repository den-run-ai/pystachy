# index_key: o[i, j], o[i, j] = v and o[i, j] op= v of a class whose __getitem__ and __setitem__
# only read the key make the key tuple in the caller's frame (Gen.stack_key). index_key.calls pins
# that total() and fill() allocate nothing (each made a tuple with pys_alloc per index before), and
# that keep() still makes its keys on the heap: its class's __getitem__ keeps them
class Grid:
    def __init__(self, n: int) -> None:
        self.n = n
        self.data: list[float] = [0.0] * (n * n)

    def __getitem__(self, key: tuple[int, int]) -> float:
        i, j = key
        return self.data[i * self.n + j]

    def __setitem__(self, key: tuple[int, int], v: float) -> None:
        self.data[key[0] * self.n + key[1]] = v


class Keep:
    def __init__(self) -> None:
        self.keys: list[tuple[int, int]] = []

    def __getitem__(self, key: tuple[int, int]) -> int:
        self.keys.append(key)
        return key[0]


def total(g: Grid) -> float:
    t = 0.0
    for i in range(g.n):
        for j in range(g.n):
            t += g[i, j]
    return t


def fill(g: Grid) -> None:
    for i in range(g.n):
        for j in range(g.n):
            g[i, j] = float(i)
            g[i, j] += 1.0


def keep(k: Keep, n: int) -> int:
    s = 0
    for i in range(n):
        s += k[i, i]
    return s


g = Grid(4)
fill(g)
print(total(g), keep(Keep(), 3))
