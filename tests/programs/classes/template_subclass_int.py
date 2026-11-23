# An int field of a template hierarchy's specialization, in a module whose ints are checked
# 64-bit ints: arithmetic through the base's and the subclasses' methods, near the limits (#962).
class Counter:
    def __init__(self, start):
        self.count = start

    def bump(self, k: int) -> None:
        self.count = self.count * k

    def half(self) -> int:
        return self.count // 2


class Doubler(Counter):
    def bump(self, k: int) -> None:
        self.count = self.count * k * 2


class Negative(Counter):
    def __init__(self, start: int) -> None:
        super().__init__(-start)

    def half(self) -> int:
        return -(self.count // -2)


cs = [Counter(3), Doubler(5), Negative(7)]
for c in cs:
    c.bump(10)
    print(type(c).__name__, c.count, c.half(), c.count % 7, -c.count >> 1)
d = Doubler(1 << 40)
d.bump(1 << 21)
print(d.count, d.count == (1 << 62), d.half())
n = Negative(9223372036854775807)
print(n.count, n.half(), n.count - 1)
