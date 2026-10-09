# listget (docs/typed-ir.md 7.1): a for loop over a list tests its index against the list's
# length, then reads that item at once, with no op between that may shorten a list. That read
# needs no bounds check, and lowers to an inline load: listget.calls pins that these functions
# call no pys_list_get (with PYSTACHY_OPT=-listget, each loop would call it).
class Box:
    def __init__(self, xs: list[float]) -> None:
        self.xs = xs

    def total(self) -> float:
        s = 0.0
        for x in self.xs:
            s += x
        return s


def first_set(xs: list[bool]) -> bool:
    for x in xs:
        if x:
            return True
    return False


def dot(xs: list[float], ys: list[float]) -> float:
    s = 0.0
    for x, y in zip(xs, ys):  # each list's own test, then both reads
        s += x * y
    return s


def weighted(xs: list[float]) -> float:
    s = 0.0
    for i, x in enumerate(xs, 1):  # the read follows the start's overflow check
        s += x * i
    for x in reversed(xs):  # an index counting down, tested against the current length
        s = s * 0.5 + x
    return s


def grow(xs: list[float]) -> None:
    for x in xs:  # the append comes after the read
        if x < 4.0:
            xs.append(x + 1.0)


def named(xs: list[str]) -> bool:
    return any(xs)  # any() steps through a list of str in a loop of its own


def other(xs: list[float], i: int) -> float:
    for x in xs:
        if x > 0.0:
            return xs[i]  # not the loop's index: checked
    return 0.0
