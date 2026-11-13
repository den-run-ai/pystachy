# Orders that a wrong TBAA tag of a list's length, items pointer or item would change. Runtime list
# code (an item assignment, append, insert, pop, sort, extend) writes between the program's own reads
# of the same list, through one name or two, in loops whose reads LLVM could otherwise keep in
# registers; appends move the items array. Every read must see the write before it.
class Holder:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs
        self.total = 0


def pin(xs: list[int], n: int) -> int:
    # (a constant index: the read after inlined pys_list_set's store is at the same address)
    t = 0
    for i in range(n):
        a = xs[0]
        xs[0] = a + i
        t += xs[0] + len(xs)
    return t


def pin_float(xs: list[float], n: int) -> float:
    s = 0.0
    for i in range(n):
        xs[1] = xs[1] * 0.5 + i
        s += xs[1] + xs[0]
    return s


def twin(xs: list[int], ys: list[int], n: int) -> int:
    # (two names: LLVM cannot relate their items, so only the tags say whether xs's store reaches
    # ys's read; with one list for both, it must)
    t = 0
    for i in range(n):
        a = ys[0]
        xs[0] = a + i
        t += ys[0] * 2 + ys[1]
    return t


def twin_float(xs: list[float], ys: list[float], n: int) -> float:
    s = 0.0
    for i in range(n):
        xs[1] = ys[1] * 0.5 + i
        s += ys[1] + ys[0]
    return s


def relay(xs: list[int], ys: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        k = (i * 7) % len(xs)
        xs[k] = xs[k] + i
        t += xs[k] * 3 + len(ys)
        if i % 5 == 0:
            ys.append(i)
    return t


def shuffle(xs: list[float], n: int) -> float:
    s = 0.0
    for i in range(n):
        j = (i * 13) % len(xs)
        xs[j] = xs[len(xs) - 1 - j] + 0.5
        s += xs[j] + xs[0]
        if i % 7 == 3:
            xs.insert(0, s)
        if i % 11 == 6:
            xs.pop()
    return s


def through(h: Holder, ys: list[int], n: int) -> int:
    for i in range(n):
        h.xs[i % len(h.xs)] = i
        h.total += h.xs[i % len(h.xs)] + len(ys)
        if i == n // 2:
            h.xs.sort(reverse=True)
            ys.extend(h.xs[:3])
            ys.pop(0)
    return h.total


print(pin([3, 1, 4], 30), pin_float([0.5, 2.0], 20))
p = [3, 1, 4]
q = [0.5, 2.0]
print(twin(p, p, 30), p, twin([9, 9], p, 5), p, twin_float(q, q, 20), q)
a = [1, 2, 3, 4, 5]
print(relay(a, a, 40), len(a), a[:8], a[-3:])
b = [10, 20, 30]
print(relay(a, b, 25), len(b), b[-4:])
c = [0.25 * k for k in range(9)]
print(shuffle(c, 50), len(c), c[:4])
h = Holder([5, 3, 8, 1])
print(through(h, h.xs, 12), h.xs)
h2 = Holder([2, 4, 6])
d = [7, 7]
print(through(h2, d, 9), h2.xs, d)
