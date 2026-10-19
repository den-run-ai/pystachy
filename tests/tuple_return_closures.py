# Returned tuples by value (tupleret) in the shapes that tests/tuple_return_values.py does not
# reach: closures (from a factory, nested, a lambda, one with a nonlocal), starred unpacking
# targets, and a generator that unpacks a returned tuple across its yields, with allocations in
# between. Each call here only reads the slots, so each is lowered by value.
import sys


def make_stepper(m: int):
    def step(x: int, y: int) -> tuple[int, int]:
        return (y, (x + y) % m)
    return step


def outer(n: int) -> int:
    def pair(k: int) -> tuple[int, str]:
        return k * 2, str(k)
    total = 0
    for k in range(n):
        a, b = pair(k)
        total += a + len(b)
    return total


def three(k: int) -> tuple[int, int, int]:
    return k, k + 1, k + 2


def starred(n: int) -> list[int]:
    out = []
    for k in range(n):
        a, *rest = three(k)
        *init, c = three(k)
        out.append(a + sum(rest) + c + len(init))
    return out


def counter():
    count = 0

    def bump(d: int) -> tuple[int, int]:
        nonlocal count
        count += d
        return count, count * 2
    return bump


def strs(k: int) -> tuple[str, list[int]]:
    return "s" * k, [k] * k


def walk(n: int):
    for k in range(n):
        s, xs = strs(k + 1)
        yield s
        junk = [str(i) for i in range(30)]
        yield str(xs) + junk[k % 30]


st = make_stepper(1000003)
x, y = 0, 1
for _ in range(10 * len(sys.argv)):
    x, y = st(x, y)
print(x, y, outer(10), starred(5))
swap = lambda p, q: (q, p)
u, v = swap(1, 2)
print(u, v)
b = counter()
p, q = b(3)
r, s = b(4)
print(p, q, r, s)
print(list(walk(4)))
