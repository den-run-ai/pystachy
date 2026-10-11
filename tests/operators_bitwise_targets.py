# &= |= ^= <<= on a field, a list item, a dict value and through __getitem__/__setitem__: each
# target's parts are evaluated once, then the in-place method (or the binary one) runs
class M:
    def __init__(self, n: int) -> None:
        self.n = n

    def __xor__(self, o: "M") -> "M":
        print("xor", self.n, o.n)
        return M(self.n ^ o.n)

    def __ilshift__(self, k: int) -> "M":
        print("ilshift", self.n, k)
        self.n <<= k
        return self

    def __or__(self, o: "M") -> "M":
        print("or", self.n, o.n)
        return M(self.n | o.n)

    def __repr__(self) -> str:
        return f"M({self.n})"


class Box:
    def __init__(self) -> None:
        self.m = M(5)


class Grid:
    def __init__(self) -> None:
        self.cells = [M(1), M(2)]

    def __getitem__(self, i: int) -> M:
        print("get", i)
        return self.cells[i]

    def __setitem__(self, i: int, v: M) -> None:
        print("set", i, v)
        self.cells[i] = v


def key(k: int) -> int:
    print("key", k)
    return k


def box(b: Box) -> Box:
    print("box")
    return b


def operand(k: int) -> M:
    print("operand", k)
    return M(k)


bx = Box()
box(bx).m ^= operand(3)
print(bx.m)
ms = [M(1), M(2)]
ms[key(1)] ^= operand(7)
ms[key(0)] <<= 4
print(ms)
d = {"a": M(9)}
d["a"] ^= M(1)
d["a"] <<= 1
print(d)
g = Grid()
g[key(1)] |= operand(4)
g[0] <<= 2
print(g.cells)
