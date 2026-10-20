# Fields that __init__ types by its value and other code gives a value of another type: the
# union of both, in the class and its template's specializations.
class P:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def move(self, dx: float) -> None:
        self.x = self.x + dx


class Counter:
    def __init__(self) -> None:
        self.n = 0

    def scale(self, k: float) -> None:
        self.n = self.n * k


p = P(0, 0)
print(p.x, p.y)
p.x = 1.5
p.move(1.0)
print(p.x, p.y)
q = P(2, 3)
print(q.x + q.y)
c = Counter()
c.scale(2.0)
print(c.n)
c.n = 3
c.scale(0.5)
print(c.n)
