# math.hypot and math.dist scale their coordinates by a power of two around the largest one:
# where that one is subnormal (below 2**-1024 they are all first brought up by 2**1022), where
# the scale itself is subnormal (a largest coordinate from 2**1022 on), and in between. Results
# are compared by their bits, for two coordinates, three, and more than sixteen.
import math

seed = 2024


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


def part() -> float:
    f = (rnd() + 1) / 2147483649.0
    return f if rnd() % 2 == 0 else -f


def mix(h: int, s: str) -> int:
    for c in s:
        h = (h * 131 + ord(c)) % 1000000007
    return h


edges = [5e-324, 1e-323, 2.0 ** -1073, 2.0 ** -1025, 2.0 ** -1024, 2.0 ** -1023, 2.0 ** -1022, 2.0 ** -1021,
         1.5 * 2.0 ** -1024, 0.75 * 2.0 ** -1022, 2.0 ** 1021, 2.0 ** 1022, 2.0 ** 1023, 1.5 * 2.0 ** 1022,
         8.98846567431158e307, 1.7976931348623157e308]
for e in edges:
    a = e * 0.75
    print(e.hex(), math.hypot(e, e).hex(), math.hypot(e, a).hex(), math.hypot(a, -e, a).hex(),
          math.dist([e, 0.0], [0.0, a]).hex(), math.dist([e, a, 0.0], [0.0, 0.0, -a]).hex(),
          math.hypot(a, a, a, a, e, a, a, a, a, a, a, a, a, a, a, a, a, a).hex())

# the ends of the exponent's range first, then the middle
for lo, span in [(-1074, 60), (-1030, 12), (1004, 18), (-520, 1040)]:
    h = 0
    for i in range(3000):
        base = lo + rnd() % span
        n = 2 + rnd() % 19
        p: list[float] = []
        q: list[float] = []
        for j in range(n):
            p.append(part() * 2.0 ** (base + rnd() % 3) * 2.0)
            q.append(part() * 2.0 ** (base + rnd() % 3) * 2.0 if rnd() % 4 > 0 else 0.0)
        zero = [0.0] * n
        h = mix(h, math.dist(p, q).hex())
        h = mix(h, math.dist(p, zero).hex())
        h = mix(h, math.hypot(p[0], q[0]).hex())
        h = mix(h, math.hypot(p[0], p[1], q[1]).hex())
    print(lo, span, h)

# an inf wins over a nan, in any position; then a nan; a zero vector and a single coordinate
inf = math.inf
nan = math.nan
none: list[float] = []
print(math.dist([nan, 1.0, inf], [0.0, 0.0, 0.0]), math.dist([1.0, nan], [0.0, -inf]), math.dist([nan, 1.0], [0.0, 2.0]),
      math.dist([inf], [inf]), math.dist([1e308, -1e308], [-1e308, 1e308]), math.dist(none, none), math.dist([-0.0], [0.0]),
      math.dist([-3.5], [1.0]), math.dist([0.0, 0.0], [0.0, -0.0]), math.hypot(nan, inf, 1.0), math.hypot(1.0, nan, 2.0))
print(math.copysign(1.0, math.hypot(nan, 1.0)), math.copysign(1.0, math.hypot(-nan, 1.0, 2.0)), math.copysign(1.0, math.dist([nan], [-1.0])))
try:
    print(math.dist([1.0, 2.0], [1.0]))
except ValueError as err:
    print("ValueError:", err)
