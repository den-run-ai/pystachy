# A function whose every return is a new tuple display returns its slots by value to the calls that
# only read them (tupleret, docs/typed-ir.md): an unpacking, a constant index, a loop over the
# tuple. Its other calls get the tuple, as before. What the program sees must not change: values,
# evaluation order, exceptions, and the identity of a tuple that a function returns again.
import sys


def step(x: int, y: int) -> tuple[int, int]:
    return (y, (x + y) % 1000003)


def run(n: int) -> int:
    x, y = 0, 1
    for _ in range(n):
        x, y = step(x, y)
    return x


def fibpair(n: int) -> tuple[int, int]:
    if n == 0:
        return (0, 1)
    a, b = fibpair(n - 1)
    return (b, a + b)


def parse(s: str, i: int) -> tuple[str, int]:
    j = i
    while j < len(s) and s[j] != ",":
        j += 1
    if j == i:
        raise ValueError(f"empty field at {i}")
    return s[i:j], j + 1


def fields(s: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(s):
        w, i = parse(s, i)
        out.append(w)
    return out


def minmax(xs: list[float]) -> tuple[float, float, bool]:
    lo = xs[0]
    hi = xs[0]
    for x in xs:
        lo = min(lo, x)
        hi = max(hi, x)
    return (lo, hi, lo == hi)


def wrapped(k: int) -> tuple[list[int], str, bool]:
    return [k] * 3, "k" * k, k > 1


SAVED = (1, 2)


def saved(fresh: bool) -> tuple[int, int]:
    if fresh:
        return (3, 4)
    return SAVED


class Box:
    def __init__(self, lo: int, hi: int) -> None:
        self.lo = lo
        self.hi = hi

    def bounds(self) -> tuple[int, int]:
        return (self.lo, self.hi)

    def grow(self, d: int) -> None:
        self.lo, self.hi = self.lo - d, self.hi + d


class Loud:
    def __init__(self) -> None:
        self.seen: list[str] = []

    @property
    def a(self) -> int:
        return 0

    @a.setter
    def a(self, v: int) -> None:
        self.seen.append(f"a={v}")

    @property
    def b(self) -> int:
        return 0

    @b.setter
    def b(self, v: int) -> None:
        if v < 0:
            raise ValueError("b < 0")
        self.seen.append(f"b={v}")


def signs(x: int) -> tuple[int, int]:
    return (x, -x)


n = 1000 * len(sys.argv)
print(run(n))
print(fibpair(50))
a, b = fibpair(60)
print(a, b, fibpair(10)[1])
print(fields("alpha,beta,gamma"))
try:
    print(fields("x,,y"))
except ValueError as e:
    print("ValueError:", e)
lo, hi, flat = minmax([3.5, -1.25, 9.0])
print(lo, hi, flat, minmax([2.0])[2])
xs, s, z = wrapped(2)
xs.append(7)
print(xs, s, z)
keep = [wrapped(k) for k in range(3)]  # (calls whose tuples escape: the tuple is made)
print(keep)
for v in step(5, 8):
    print(v)
t = step(1, 2)
print(t, t == step(1, 2), t is t)
print(saved(False) is SAVED, saved(True) is SAVED, saved(True) == (3, 4))
p, q = saved(False)
print(p, q)
box = Box(1, 5)
box.grow(2)
lo2, hi2 = box.bounds()
print(lo2, hi2, box.bounds())
loud = Loud()
try:
    loud.a, loud.b = signs(-4)
    loud.a, loud.b = signs(4)
except ValueError as e:
    print("ValueError:", e, loud.seen)
total = 0
for k in range(200):
    u, w = wrapped(k % 4)[1], step(k, k)[0]
    total += len(u) + w
print(total)
