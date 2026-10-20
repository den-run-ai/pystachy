# A := that may not run (after and/or, in one arm of an if-else, in a chained comparison past the
# first, in a comprehension over nothing, in an assert's message) leaves its name unbound, or as it
# was: a later read raises UnboundLocalError in a function and NameError in module code, as in
# CPython, and sees the value it holds, not one a test narrowed before


def cond(flag: bool) -> None:
    try:
        if flag and (w := 10):
            print("w", w)
        print("after", w)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


cond(True)
cond(False)


def either(flag: bool) -> None:
    try:
        print((a := 1) if flag else (b := 2))
        print(a)
        print(b)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


either(True)
either(False)


def chained(x: int) -> None:
    try:
        if 0 < x < (top := 10):
            print("in range")
        print(top)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


chained(5)
chained(-1)


def comp(xs: list[int]) -> None:
    try:
        print([(seen := x) for x in xs])
        print(seen)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)


comp([4, 5])
comp([])


def loop(xs: list[int]) -> int:
    best = -1
    for x in xs:
        if x > 2 or (small := x) < 0:
            best = x
    try:
        return small
    except UnboundLocalError:
        return best


print(loop([1, 5]), loop([5, 7]))
flags = [False]
if flags[0] or (got := 3):
    print("got", got)
if flags[0] and (never := 1):
    pass
try:
    print(never)
except NameError as e:
    print("NameError:", e)


def asserted(x: int) -> None:
    try:
        assert x > 0, (msg := "not positive")
        print(msg)
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)
    except AssertionError as e:
        print("AssertionError:", e)


asserted(1)
asserted(-1)


def rebound(y: int) -> None:
    z: int | None = None
    if 0 < y < (z := 10):
        print("in range", z)
    print(z)
    w: int | None = 3
    if w is not None and y > 0 or (w := None) is None:
        print("w", w)


rebound(5)
rebound(-5)
