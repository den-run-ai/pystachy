# tupleret (tuple_return_closures.calls) in the shapes of tests/tuple_return_closures.py: closures
# (from a factory, nested, a lambda, one with a nonlocal), starred targets, and a generator that
# unpacks a returned tuple across its yields. Each call only reads the slots, so each callee gets a
# by-value body (@v.c.<n>.1, @v.f.three, @v.f.strs) beside the wrapper that makes the tuple; the
# contract fails if one of them goes back to returning a heap tuple.
def make_stepper(m: int):
    def step(x: int, y: int) -> tuple[int, int]:
        return (y, (x + y) % m)
    return step


def outer(n: int) -> int:
    def pair(k: int) -> tuple[int, int]:
        return k * 2, k + 1
    total = 0
    for k in range(n):
        a, b = pair(k)
        total += a + b
    return total


def three(k: int) -> tuple[int, int, int]:
    return k, k + 1, k + 2


def starred(n: int) -> int:
    total = 0
    for k in range(n):
        a, *rest = three(k)
        *init, c = three(k)
        total += a + len(rest) + c + len(init)
    return total


def counter():
    count = 0

    def bump(d: int) -> tuple[int, int]:
        nonlocal count
        count += d
        return count, count * 2
    return bump


def strs(k: int) -> tuple[str, int]:
    return "s" * k, k


def walk(n: int):
    for k in range(n):
        s, m = strs(k + 1)
        yield len(s) + m


st = make_stepper(1000003)
x, y = st(0, 1)
swap = lambda p, q: (q, p)
u, v = swap(1, 2)
b = counter()
p, q = b(3)
print(x, y, outer(10), starred(5), u, v, p, q, list(walk(3)))
