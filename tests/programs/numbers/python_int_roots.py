# pystachy: python-int
# Promoting ints (docs/python-int.md) whose digits only a module variable, a class attribute, a
# field, a closure cell, a default or a generator's frame holds: values of the same size made
# afterwards reuse whatever memory the collector freed, so a missing root reads another value
# (with a collection at every allocation, as the test runner's GC stress runs it).
G = 0


def setg(k: int) -> None:
    global G
    G = 3 ** 200 + k


def reuse() -> int:
    t = 0
    for j in range(300):
        x = 5 ** 136 + j
        t += x % 7
    return t


class Holder:
    shared: int = 0

    def __init__(self, k: int) -> None:
        self.value = 3 ** 200 + k


def counter(k: int):
    total = 3 ** 200 + k

    def bump() -> int:
        nonlocal total
        total += 1
        return total
    return bump


def make_default(k: int):
    def f(x: int = 3 ** 200 + k) -> int:
        return x
    return f


def frames(k: int):
    x = 3 ** 200 + k
    yield 1
    yield 1 if x == 3 ** 200 + k else 0


setg(15)
Holder.shared = 3 ** 200 + 16
h = Holder(17)
b = counter(18)
d = make_default(19)
g = frames(20)
next(g)
reuse()
want = 3 ** 200
print(G - want, Holder.shared - want, h.value - want, b() - want, d() - want, next(g))
reuse()
print(G % 1000003, Holder.shared % 1000003, h.value % 1000003, b() - want, d() - want)
