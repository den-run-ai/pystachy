# list.sort, sorted and min compare objects with < only (max with >): the class's other ordering
# methods, whatever they take, are not called, so they are no error. In an imported class, one
# that Pystachy cannot compile (an __le__ without its parameter) is no error either.
from scope import sigs


class V:
    def __init__(self, x: int) -> None:
        self.x = x

    def __lt__(self, other: "V") -> bool:
        return self.x < other.x

    def __ge__(self, other: int) -> bool:
        return self.x >= other


class W:
    def __init__(self, x: int) -> None:
        self.x = x

    def __gt__(self, other: "W") -> bool:
        return self.x > other.x

    def __lt__(self, other: int) -> bool:
        return self.x < other


xs = [V(3), V(1), V(2)]
print([v.x for v in sorted(xs)], min(xs).x, V(2) >= 2)
xs.sort(reverse=True)
print([v.x for v in xs])
ws = [W(3), W(5), W(1)]
print(max(ws).x, W(1) < 2)
rs = [sigs.Ranked(2), sigs.Ranked(1)]
rs.sort()
print([r.x for r in rs], min(rs).x, sigs.Ranked(4) > 3)
