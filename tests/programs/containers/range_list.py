# list(range(a, b, s)) is allocated at its length: lengths from 0 up, both signs of step, the ends
# of the int range (each item computed with wrapping arithmetic is the item), and CPython's errors
# for a length no list can have
import sys


def build(a: int, b: int, s: int) -> int:
    return len(list(range(a, b, s)))


for a, b, s in [(0, 0, 1), (0, 1, 1), (0, 10, 1), (10, 0, -1), (0, 10, 3), (0, 10, -3), (10, -10, -7),
                (-5, 5, 2), (5, 5, -1), (3, 4, 100), (-3, -4, -100), (0, 5, 6), (1, 2, -1)]:
    print(a, b, s, list(range(a, b, s)))
print(list(range(7)), list(range(-3)), list(range(2, 9)), sorted(range(5, 0, -2)))
m = sys.maxsize
print(list(range(-m - 1, m, 2**62)))
print(list(range(m, -m - 1, -(2**62))))
print(list(range(m - 2, m)), list(range(-m - 1, -m + 1)), list(range(m, m - 3, -1)))
print(list(range(-m - 1, m, m)), list(range(m, -m - 1, -m)), list(range(-m - 1, m, -1)))
big = list(range(1000003))
print(len(big), big[0], big[500000], big[-1], sum(big))
big.append(7)
big.append(8)
print(len(big), big[-3:])
down = list(range(10, -3000000, -3))
print(len(down), down[:3], down[-3:], sum(down))
xs: list[int] = []
for k in range(40):
    xs = xs + list(range(k, k * 3, 2))
print(len(xs), sum(xs))
for a, b, s in [(0, 2**62, 1), (0, m, 1), (0, m, 16), (-m - 1, m, 1), (m, -m - 1, -1), (-m - 1, m, 2)]:
    try:
        print(build(a, b, s))
    except MemoryError:
        print("MemoryError", a, b, s)
    except OverflowError as e:
        print("OverflowError", e, a, b, s)
try:
    print(list(range(1, 5, 0)))
except ValueError as e:
    print("ValueError", e)
