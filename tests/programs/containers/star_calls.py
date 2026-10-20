# Star arguments in calls: f(*t) passes a tuple's items (or a list or tuple display's) as
# positional arguments, to any function, method, class, Callable or builtin, and *args forwards a
# function's own extra arguments; print(*xs) prints a list's items. CPython evaluates the function
# first, then the arguments in order, unpacking each star where it is
from typing import Callable


def trace(f):
    def wrapper(*args):
        print("call", f.__name__, args)
        return f(*args)
    return wrapper


@trace
def add(a, b):
    return a + b


def total(*xs):
    s = 0
    for x in xs:
        s += x
    return s


def three(a: int, b: int, c: int = 100) -> int:
    return a * 100 + b * 10 + c


class P:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def moved(self, dx: int, dy: int) -> "P":
        return P(self.x + dx, self.y + dy)


t = (1, 2, 3)
pt = (4, 5)
print(add(1, 2), add("x", "y"), total(*t), total(0, *t, 10), P(*pt).moved(*pt).x)
print(three(*t), three(*pt), three(*pt, c=7), three(1, *(2,)), three(*[7, 8, 9]), three(*(), 1, 2))
print(*t)
print(*t, sep="-", end="!\n")
xs = [3, 1, 2]
print(*xs)
print("a", *xs, "b", sep=", ")
print(*[], "only")
print(*"abc", sep="|")
words = {"k": 1, "j": 2}
print(*words)
print(max(*t), divmod(*pt), "-".join(*[["p", "q"]]))
cb: Callable[[int, int], int] = lambda x, y: x * y
pair = (6, 7)
print(cb(*pair), [g(*pair) for g in [cb, max]])
try:
    raise ValueError(*("bad", 1))
except ValueError as e:
    print(e)


def note(tag: str, v):
    print("eval", tag)
    return v


print(note("f", three)(note("a", 1), *note("t", (2, 3))))
print(note("o", P(1, 1)).moved(*note("d", (2, 2))).y)
none_t: tuple[int, int] | None = None
for k in range(4):
    try:
        if k == 0:
            three(*none_t)
        elif k == 1:
            P(*none_t)
        elif k == 2:
            print(*none_t)
        else:
            note("g", three)(*none_t)
    except TypeError as e:
        print("TypeError:", e)
try:
    raise ValueError(*none_t)
except TypeError as e:
    print("TypeError:", e)


def fk(*a, b=0, c=0):
    return a, b, c


# positional and starred arguments are evaluated before keyword ones, whatever their order
print(fk(b=note("kw", 2), *[note("star", 1)]))
print(fk(note("p", 0), b=note("kw", 2), *[note("star", 1)], c=note("kw2", 3)))
dd = {"a": 1}


def make_sep() -> str:
    dd["z"] = 2
    return "-"


# a sole star is unpacked once the keywords are evaluated
print(*dd, sep=make_sep())
ys: list[int] | None = [1]
old_ys = ys


def rebind() -> tuple[int]:
    global ys
    ys = None
    return (5,)


# o.m binds o before the arguments are evaluated
ys.append(*rebind())
print(old_ys)
