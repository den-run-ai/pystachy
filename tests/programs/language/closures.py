# Lambdas and defs inside functions: closures that read the variables of the functions around
# them when they run (each such variable lives in a cell the closures share), nonlocal, defaults
# evaluated where the def or lambda is, recursion, and closures returned, stored and passed on


def adder(n):
    return lambda x: x + n


def counter(start: int) -> list[int]:
    total = start

    def add(x):
        nonlocal total
        total += x
        return total

    out = [add(1), add(2)]
    total = 100
    out.append(add(3))
    return out


def late() -> list[int]:
    fs = []
    for i in range(3):
        fs.append(lambda: i * 10)
    i = 7
    return [f() for f in fs]


def early() -> list[int]:
    fs = []
    for i in range(3):
        fs.append(lambda i=i: i * 10)
    return [f() for f in fs]


def fib_memo(n):
    memo: dict[int, int] = {}

    def fib(k):
        if k < 2:
            return k
        if k in memo:
            return memo[k]
        r = fib(k - 1) + fib(k - 2)
        memo[k] = r
        return r
    return fib(n)


def twice(f, x):
    return f(f(x))


def compose(f, g):
    return lambda x: f(g(x))


def outer_inner_innermost(a):
    def middle(b):
        def inner(c):
            return a + b + c
        return inner
    return middle


def nonlocal_two_levels() -> int:
    n = 0

    def outer_step():
        def inner_step():
            nonlocal n
            n += 10
        inner_step()
        inner_step()
    outer_step()
    return n


def defaults_now() -> list[str]:
    tag = "a"

    def show(x, t=tag + "!"):
        return f"{x}{t}"
    tag = "b"
    first = show(1)

    def show2(x, t=tag + "?"):
        return f"{x}{t}{tag}"
    tag = "c"
    return [first, show(2), show2(3), show2(4, "-")]


def kw_and_star(prefix):
    def f(*parts, sep=", "):
        return prefix + sep.join(parts)
    return [f("a", "b"), f("x", sep="/"), f()]


class Scale:
    def __init__(self, k: int) -> None:
        self.k = k

    def apply_all(self, xs: list[int]) -> list[int]:
        return sorted(xs, key=lambda x: (x * self.k) % 7)


def scaler(sc):
    return lambda x: x * sc.k


def by_column(rows: list[tuple[str, int]], col: int) -> list[tuple[str, int]]:
    return sorted(rows, key=lambda r: r[1] * col)


def identity_checks() -> list[bool]:
    fs = []
    for _ in range(2):
        fs.append(lambda: 0)
    g = fs[0]
    return [fs[0] == fs[1], fs[0] is g, fs[1] != g]


def names() -> list[str]:
    def inner():
        pass
    lam = lambda: None
    return [inner.__name__, inner.__qualname__, lam.__name__, lam.__qualname__]


add5 = adder(5)
print(add5(1), adder(2)(3), adder("a")("b"), adder(1.5)(1))
print(counter(10), late(), early(), fib_memo(30))
print(twice(lambda s: s + s, "ab"), twice(adder(3), 1), compose(len, str)(12345), compose(adder(1), abs)(-5))
print(outer_inner_innermost(1)(2)(3), outer_inner_innermost("x")("y")("z"), nonlocal_two_levels())
print(defaults_now(), kw_and_star(">"))
s = Scale(3)
print(scaler(s)(4), s.apply_all([1, 2, 3, 4, 5, 6]))
print(by_column([("b", 2), ("a", 3), ("c", 1)], -1), identity_checks(), names())
square = lambda x: x * x
pairs = [(1, "b"), (0, "c"), (2, "a")]
print(square(7), sorted(pairs, key=lambda p: p[1]), max(pairs, key=lambda p: -p[0]), min("hello", key=lambda c: -ord(c)))
total = 0
for k in range(4):
    total += (lambda v: v * v)(k)
print(total, (lambda: "now")(), (lambda a, b=2: a * b)(5), (lambda *xs: len(xs))(1, 2, 3))
