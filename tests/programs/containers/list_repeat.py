# list * n and xs *= n (#649): one item of zero bits (0, 0.0, False, None) is not copied, as a new
# list's items are zero; other lists copy a prefix that doubles. Item kinds, -0.0 and nan, counts
# that are not powers of two, lists past the largest size class, counts <= 0, shared references,
# xs *= n on a list with vacated room and through an alias, zero items in memory that collections
# gave back, and the MemoryError bound
import math


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def same(a: float, b: float) -> bool:
    if a != a:
        return b != b
    return a == b and math.copysign(1.0, a) == math.copysign(1.0, b)


def check_floats(unit: list[float], n: int) -> str:
    xs = unit * n
    k = len(unit)
    if len(xs) != k * n:
        return "bad length " + str(len(xs))
    for i in range(len(xs)):
        if not same(xs[i], unit[i % k]):
            return "bad at " + str(i)
    return "ok " + str(len(xs))


def check_ints(unit: list[int], n: int) -> str:
    xs = unit * n
    k = len(unit)
    if len(xs) != k * n:
        return "bad length " + str(len(xs))
    for i in range(len(xs)):
        if xs[i] != unit[i % k]:
            return "bad at " + str(i)
    return "ok " + str(len(xs))


counts = [1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 17, 100, 1023, 1024, 1025, 1026, 5000]
for unit in [[0.0], [-0.0], [1.5], [math.nan], [math.inf, -0.0], [0.0, 0.0], [0.0, 1.0, 2.0], [0.5] * 7]:
    print(len(unit), [check_floats(unit, n) for n in counts])
for iunit in [[0], [1], [-1], [0, 0, 0], [3, 0], [9223372036854775807, -9223372036854775808, 0]]:
    print(len(iunit), [check_ints(iunit, n) for n in counts])

flags = [False] * 1500
truths = [True] * 1500
print(len(flags), sum(flags), any(flags), sum(truths), all(truths), [False, True] * 3)
words = ["ab"] * 2000
print(len(words), words[0] is words[1999], "".join(words[:3]), [""] * 3, ["x", "y"] * 2)
boxes = [Box(1)] * 4
boxes[0].v = 5
print([b.v for b in boxes], boxes[1] is boxes[3])
maybe: list[Box | None] = [None] * 1200
maybe[7] = Box(3)
print(len(maybe), sum([1 for m in maybe if m is None]), maybe[6] is None, maybe[7] is not None)
holes: list[int | None] = [None] * 5
print(holes, [None, 1] * 2)
grid = [[0]] * 3
grid[0].append(1)
print(grid, grid[0] is grid[2])

empty: list[int] = []
print([1, 2] * 0, [1] * -3, [0.0] * -9223372036854775807, empty * 5, empty * 9223372036854775807)
print(3 * [0], 0 * [1.5], -2 * ["a"], 2 * [7, 8])

xs = [1.0, 2.0, 3.0, 4.0, 5.0]
xs.pop()
xs.pop()
alias = xs
xs *= 3
print(xs, alias is xs, len(alias))
ws = [0.0]
ws *= 1000
print(len(ws), sum(ws), ws[999], math.copysign(1.0, ws[500]))
ns = [-0.0]
ns *= 1030
print(len(ns), math.copysign(1.0, ns[1029]), math.copysign(1.0, ns[0]))
vs = [7]
vs *= 1
us = ["a", "b"]
us *= 0
print(vs, us)
ts = [Box(2)]
ts *= 3
ts[0].v = 9
print([t.v for t in ts])


def churn(mb: int) -> float:
    # about mb MiB of lists of nonzero items that become garbage: past 32 MiB a collection runs,
    # and later lists reuse what it gave back
    t = 0.0
    for i in range(mb * 16):
        big = [1.5 + float(i)] * 8192
        small = [2.5] * 100
        t += big[i % 8192] + small[i % 100]
    return t


print(churn(40))
total = 0.0
negative = 0
nones = 0
for i in range(500):
    small = [0.0] * (1 + i % 300)
    big = [0.0] * (1100 + i)
    zs = [0] * (1 + i % 40)
    objs: list[Box | None] = [None] * (1 + i % 50)
    for v in small:
        total += v
        if math.copysign(1.0, v) < 0.0:
            negative += 1
    total += big[i] + big[-1] + float(sum(zs))
    nones += sum([1 for o in objs if o is None])
print(total, negative, nones)


def rep(x: list[int], n: int) -> list[int]:
    return x * n


for n in [4611686018427387904, 9223372036854775807]:
    try:
        print(len(rep([0], n)))
    except MemoryError:
        print("MemoryError", n)
    try:
        print(len(rep([1, 2], n)))
    except MemoryError:
        print("MemoryError pair", n)
one = [5]
try:
    one *= 4611686018427387904
except MemoryError:
    print("MemoryError in place", one)
