# More closures: optional variables, exceptions through closures, a lambda in a finally block
# (compiled for each way out), loop variables a closure reads after the loop changes them, closures
# in dicts and passed through functions that do not use them, a function defined after the closure
# that calls it, and one closure called with arguments of several types
import sys


def first_upper(name: str | None) -> str:
    def get() -> str:
        if name is None:
            return "-"
        return name.upper()
    return get()


def checked(xs: list[int]) -> list[str]:
    out: list[str] = []

    def must_be_positive(x):
        if x <= 0:
            raise ValueError(f"bad {x}")
        return x

    for x in xs:
        try:
            out.append(str(must_be_positive(x)))
        except ValueError as e:
            out.append(str(e))
    return out


def with_finally(n: int) -> int:
    k = n
    try:
        if n > 1:
            return n
    finally:
        g = lambda: k * 2
        k = g()
    return k


def watch() -> list[int]:
    seen: list[int] = []
    i = 0
    read = lambda: i
    while i < 3:
        seen.append(read())
        i += 1
    seen.append(read())
    return seen


def table() -> dict[str, int]:
    double = lambda x: x * 2
    ops = {"double": double, "again": double}
    return {"d": ops["double"](21), "s": ops["again"](1)}


def passthrough(k):
    def middle():
        def inner():
            return k + 1
        return inner
    return middle()()


def poly(tag):
    show = lambda x: f"{tag}:{x}"
    return [show(1), show("a"), show(2.5), show([1])]


def later_fn(x):
    f = lambda: helper(x)
    return f()


def helper(v):
    return v * 3


def summed(xs, k):
    scale = lambda v: v * k
    return sum(scale(x) for x in xs), max(scale(x) for x in xs)


print(first_upper("ann"), first_upper(None), checked([3, -1, 2]))
print(with_finally(5), with_finally(1), watch(), table())
print(passthrough(41), poly("p"), later_fn(7), summed([1, 2, 3], 10))
try:
    print((lambda: 1 // 0)())
except ZeroDivisionError as e:
    print("caught", e)
print((lambda: sys.maxsize)() > 0)


# a variable that a closure assigns (nonlocal) is not narrowed by a test: a call may change it
def reset_between(s: str | None) -> str:
    x = s

    def reset() -> None:
        nonlocal x
        x = None

    if x is not None:
        reset()
        return x.upper()
    return "none"


try:
    print(reset_between("a"))
except AttributeError as e:
    print("AttributeError:", e)
