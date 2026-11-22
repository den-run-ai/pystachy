# pystachy: python-int
# An int field of a template hierarchy's specialization in a module that opts in to promoting
# ints: a result beyond 64 bits is CPython's (#962).
class Counter:
    def __init__(self, start):
        self.count = start

    def bump(self, k: int) -> None:
        self.count = self.count * k


class Doubler(Counter):
    def bump(self, k: int) -> None:
        self.count = self.count * k * 2


class Fixed(Counter):
    def __init__(self) -> None:
        super().__init__(7)


cs = [Counter(3), Doubler(5), Fixed()]
for c in cs:
    c.bump(10)
    print(type(c).__name__, c.count)
d = Doubler(1 << 40)
d.bump(1 << 30)
print(d.count)
d.bump(1 << 62)
print(d.count, d.count % 1000003)
