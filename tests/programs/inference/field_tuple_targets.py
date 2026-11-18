# Fields stored through a tuple or list target in __init__ (self.a, self.b = v) take the types of
# v's items: a display's one by one, a tuple's by position, as mypyc's RStruct stores
# self.offsets, self.size = compute_aligned_offsets_and_size(types), another iterable's all
# alike, also in nested targets. A later store may widen one, as it may a field that self.k = v
# stores, and types one whose item has no type known here (ends[-1]).
def layout(sizes: list[int]) -> tuple[list[int], int]:
    offsets: list[int] = []
    total = 0
    for s in sizes:
        offsets.append(total)
        total += s
    return offsets, total


class Struct:
    def __init__(self, name: str, sizes: list[int]) -> None:
        self.name = name
        self.offsets, self.size = layout(sizes)


class Parts:
    def __init__(self, name: str, ends: list[str], point: tuple[int, tuple[str, float]], code: str, k: int) -> None:
        self.name, self.size = name, len(ends)
        [self.x, (self.label, self.weight)] = point
        self.lo, self.hi = ends
        self.c1, self.c2 = code
        self.count, self.done = self.size * 2, False
        self.done = self.count > 2
        self.first, self.last = self.size, ends[-1]
        if k > 1:
            self.count = k / 2
            self.last = name


s = Struct("pt", [8, 4, 4])
print(s.name, s.offsets, s.size)
s.offsets.append(s.size)
print(s.offsets)
p = Parts("p", ["b", "a"], (3, ("w", 0.5)), "ok", 1)
print(p.name, p.size, p.x, p.label, p.weight, p.lo, p.hi, p.c1, p.c2, p.count, p.done, p.first, p.last)
p.x += 1
q = Parts("q", ["c", "d"], (0, ("v", 1.5)), "no", 5)
print(p.x, p.label.upper(), p.weight * 2, q.count, q.last)
