# unionslots (docs/typed-ir.md 7.1): a local of a union of numbers keeps its value in two slots,
# its tag and its payload, instead of a box per value. A loop that adds to an int | float total
# makes no box: the one pys_ubox of acc and mixed is the return's. A print reads the tag and the
# payload (keep, shown), and so does a call given the float that t += x narrows t to (narrowed).
# A union value that leaves the local in a loop (kept) keeps the boxes, since a box made at each
# load could be more than the stores made. unionslots.calls pins them.
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


def kept(xs: list[int | float]) -> None:
    t: int | float = 0
    for x in xs:
        keep(t)
        t = t + x


def shown(xs: list[float]) -> None:
    t: int | float = 0
    for x in xs:
        t += x
        print(t)


print(acc([0.5, 1.5]), mixed([1, 2.5]))
narrowed([0.5])
kept([1, 0.5])
shown([0.5])
