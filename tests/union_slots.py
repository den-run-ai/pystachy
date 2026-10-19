# Locals of a union of numbers that unionslots (docs/typed-ir.md 7.1) keeps in tag and payload slots:
# totals of mixed sums, values printed in a loop, calls' boxes stored and copied, bools, an
# exception handler in the loop and a conditional expression. Run with PYSTACHY_OPT=-unionslots too.
def mixed(xs: list[int | float]) -> int | float:
    t: int | float = 0
    for x in xs:
        t = t + x
    return t


def shown(xs: list[float]) -> int | float:
    t: int | float = 0
    for x in xs:
        t += x
        print(t)
    return t


def half(n: int) -> int | float:
    if n % 2 == 0:
        return n // 2
    return n / 2


def calls(n: int) -> int | float:
    t: int | float = 0
    for i in range(n):
        t = half(i)
    u: int | float = t
    return u


def flags(xs: list[bool | int]) -> bool | int:
    t: bool | int = False
    for x in xs:
        if x:
            t = x
    return t


def caught(xs: list[float]) -> int | float:
    t: int | float = 0
    for x in xs:
        try:
            if x < 0:
                raise ValueError("neg")
            t += x
        except ValueError:
            t = t * 2
    return t


def never(n: int) -> int | float:
    t: int | float = 1
    while n > 0:
        n -= 1
        t = t * 0.5 if n % 3 == 0 else t + 1
    return t


print(mixed([1, 2.5, 3]), mixed([]), mixed([1, 2]))
print(shown([0.5, 1.0]))
print(calls(5), calls(0), calls(4))
print(flags([True, 0, 2]), flags([]))
print(caught([1.5, -1.0, 2.0]), caught([]))
print(never(5), never(0))
