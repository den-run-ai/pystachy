# Methods without a return annotation that return another one's fresh list where a joined list
# is kept: each returns the joined list type, as if annotated, as functions do
# (join_return_chain.py), also a base class's method called on an object of a class that no
# class derives from. The values keep their types.
class Ops:
    def scale(self, u, k):
        return [x * k for x in u]

    def twice(self, u):
        return self.scale(self.scale(u, 0.5), 2.0)


class Base:
    def grow(self, u, k):
        return [x * k for x in u]


class Steps(Base):
    def __init__(self, k: float) -> None:
        self.k = k

    def step(self, u):
        return self.grow(u, self.k)


def run(n: int, rounds: int):
    ops = Ops()
    u = [1] * n
    for _ in range(rounds):
        u = ops.twice(u)
    return u


def walk(n: int, rounds: int):
    s = Steps(1.5)
    u = [2] * n
    for _ in range(rounds):
        u = s.step(u)
    return u


print(run(3, 2), run(2, 0), run(0, 1))
print(walk(2, 2), walk(1, 0))
