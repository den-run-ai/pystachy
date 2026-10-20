# unionslots (docs/typed-ir.md 7.1): a local of a union of numbers keeps its value in two slots,
# its tag and its payload, instead of a box per value. A loop that adds to an int | float total
# makes no box: the one pys_ubox of acc and mixed is the return's. A print reads the tag and the
# payload (keep, shown), and so does a call given the float that t += x narrows t to (narrowed).
# A value that leaves the local is boxed where it is loaded, so a slot is split only where each
# such box stands for one that a store no longer makes: paid's loop boxes once a pass, for the
# call, instead of at its store. Where the stores' boxes are made elsewhere (by a call in passed,
# a parameter in param, a list in item) or more such loads follow a store (twice, thrice), the
# slot stays, with main's boxes. unionslots.calls pins them.
def acc(xs: list[float]) -> int | float:
    t: int | float = 0
    for x in xs:
        t += x
    return t


def mixed(xs: list[int | float]) -> int | float:
    t: int | float = 0
    for x in xs:
        t = t + x
    return t


def keep(v: int | float) -> None:
    print(v)


def narrowed(xs: list[float]) -> None:
    t: int | float = 0
    for x in xs:
        t += x
        keep(t)


def paid(xs: list[int | float]) -> None:
    t: int | float = 0
    for x in xs:
        keep(t)
        t = t + x


def twice(xs: list[int | float]) -> None:
    t: int | float = 0
    for x in xs:
        keep(t)
        keep(t)
        t = t + x


def half(n: int) -> int | float:
    if n % 2 == 0:
        return n // 2
    return n / 2


def passed(n: int) -> int | float:
    t: int | float = half(n)
    return t


def param(v: int | float) -> int | float:
    t: int | float = v
    return t


def item(xs: list[int | float]) -> int | float:
    t: int | float = xs[0]
    return t


def thrice(a: int, b: float) -> None:
    t: int | float = a
    if b > 0:
        t = b
    keep(t)
    keep(t)
    keep(t)


def shown(xs: list[float]) -> None:
    t: int | float = 0
    for x in xs:
        t += x
        print(t)


print(acc([0.5, 1.5]), mixed([1, 2.5]))
narrowed([0.5])
paid([1, 0.5])
twice([1, 0.5])
print(passed(3), param(2.5), item([1, 2.5]))
thrice(1, 2.0)
shown([0.5])
