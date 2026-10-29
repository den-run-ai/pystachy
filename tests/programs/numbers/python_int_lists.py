# pystachy: python-int
# A list of ints holds promoting ints past 64 bits, as CPython's holds any int: displays,
# comprehensions, append(), insert(), item and slice assignment, extend() and +=, reads by index,
# iteration and unpacking, pop(), remove() and del, in, index() and count() (also of floats),
# sorting (by key too), min(), max() and sum(), ==, < and repr(), copies, slices, + and *, and
# -2**63 itself, which an item past 64 bits holds in its slot (tests/deviations/python_int_limits.py
# has the places that keep 64-bit ints)
big = 2 ** 64
xs = [1, big, -big, 2 ** 63, -2 ** 63, 2 ** 63 - 1]
print(xs, len(xs))
print(xs[1], xs[-1], xs[1] + 1, xs[2] * 3, xs[4] - 1, xs[3] // 2)
for x in xs:
    print(x, x > 0, x * x)
a, b, *rest = xs
print(a, b, rest)
xs.append(big * big)
xs.insert(0, -big - 1)
xs[2] = big + 5
print(xs)
print(xs.pop(), xs.pop(0), xs)
print(big in xs, big + 5 in xs, 7 in xs, -2 ** 63 in xs, -2 ** 63 - 1 in xs, 2 ** 63 in xs)
print(float(2 ** 63) in xs, 2.0 ** 64 in [big], 2.5 in xs, float("nan") in xs)
print(xs.index(-big), xs.index(2 ** 63), xs.index(-2 ** 63), xs.count(2 ** 63), xs.count(-2 ** 63), xs.count(big))
print(sorted(xs), min(xs), max(xs), sum(xs), sum(xs, big))
ys = xs[:]
ys.sort(reverse=True)
print(ys, ys == sorted(xs, reverse=True), ys < xs, ys > xs)
print([big] == [big], [big] == [big + 1], [big] == [2.0 ** 64], [big, 1] < [big, 2], [big] < [big + 1], [-big] < [1])
print(ys + [big], [big] * 3, ys[1:3], ys[::2], list(reversed(ys)))
print(sorted(xs, key=lambda v: -v), sorted([3, -big, big, 0], key=abs))
mixed = [big, -big, 0, -2 ** 63, 2 ** 63 - 1, big * big, -big * big, 5, big, -big, 2 ** 63]
print(sorted(mixed), sorted(mixed, reverse=True))
print(sorted([big + 1, big, big - 1]), sorted([-big, -big - 1, -big + 1], reverse=True), sorted([big]))
zs = [i * big for i in range(4)]
zs.extend([big, 1])
zs += [-big]
zs[1:3] = [7, big * 7, 8]
del zs[0]
zs.remove(big)
print(zs, len(zs))
zs.reverse()
print(zs, zs.copy() == zs, list(zs) is zs)
grid = [[big, 1], [2, big + 1]]
grid[1][0] = grid[0][0] * 2
print(grid, grid[1][0] - grid[0][0], [row[0] for row in grid])
try:
    print([big].index(big + 1))
except ValueError as e:
    print(e)
try:
    xs.remove(big + 2)
except ValueError as e:
    print(e)
empty: list[int] = []
try:
    print(min(empty))
except ValueError as e:
    print(e)


class Bag:
    def __init__(self) -> None:
        self.items: list[int] = []

    def add(self, n: int) -> None:
        self.items.append(n * big)

    def total(self) -> int:
        return sum(self.items)


def squares(n: int) -> list[int]:
    return [i ** 30 for i in range(n)]


bag = Bag()
for i in range(3):
    bag.add(i + 1)
print(bag.items, bag.total(), bag.items.pop(), squares(4)[-1], max(squares(5)))
print(max(i * big for i in range(5)), min(-i * big for i in range(1, 4)))

# A module without the opt-in can list a wide value returned by a promoting module.
from fixed_import_list import show
show()
