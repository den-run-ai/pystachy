# A template's function that returns an empty container without a type before the code that
# gives it one (further on in a loop: a call that fills it, an alias, a store; or another
# return of a list or dict) returns that type: the calls see what the container holds.
def helper(xs: list[str]) -> None:
    xs.append("s")


def collect(n):
    out = []
    i = 0
    while True:
        if i == n:
            return out
        helper(out)
        i += 1


print(collect(2), collect(0))


def fill(d: dict[str, str]) -> None:
    d["key"] = "value"


def build(n):
    out = {}
    i = 0
    while True:
        if i == n:
            return out
        fill(out)
        i += 1


r = build(1)
print(len(r), r, r["key"], build(0))


def gather(*args):
    out = []
    for a in args:
        out.append(a)
    i = 0
    while True:
        if i == 2:
            return out
        helper(out)
        i += 1


print(gather())
STORE: dict[str, list[float]] = {}


def keep(n):
    out = []
    i = 0
    while True:
        if i == n:
            return out
        STORE["k"] = out
        out.append(2.5)
        i += 1


print(keep(1), STORE)


def direct(n):
    out = []
    i = 0
    while True:
        if i == n:
            return out
        out.append("d")
        i += 1


print(direct(2))


def two(flag, n):
    a = []
    b = []
    i = 0
    while True:
        if i == n:
            if flag:
                return a
            return b
        helper(a)
        i += 1


print(two(True, 2), two(False, 2))


def pick(flag):
    out = []
    if flag:
        return out
    return [1.5]


print(pick(True), pick(False))


def first(*args):
    out = []
    for a in args:
        out.append(a)
    if len(out) > 0:
        return out
    return ["none"]


print(first())


def other(flag):
    out = []
    if flag:
        return out
    xs = ["a", "b"]
    return xs


x = other(True)
x.append("z")
print(x, other(False))
