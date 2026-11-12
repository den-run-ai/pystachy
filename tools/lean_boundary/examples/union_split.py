"""Split union locals: a union of numbers or an optional number held as two int slots, its tag
(None: 0) and its payload bits (optimizations.gen_unionslots)."""


def accumulate(n: int) -> int | float:
    total: int | float = 0
    for i in range(n):
        if i % 2:
            total = total + 0.5
        else:
            total = total * 2
    return total


def maybe(flag: bool, k: int) -> str:
    found: int | None = None
    if flag:
        found = k
    if found is not None:
        return str(found % 3)
    return "none"


def bump(value: int | float) -> int | float:
    return value + 1


def describe(value: int | float) -> str:
    if isinstance(value, int):
        return "int " + str(value)
    return "float " + str(value)


print(accumulate(5), accumulate(4), maybe(True, 7), maybe(False, 7))
print(describe(bump(3)), describe(bump(2.5)), describe(accumulate(3)))
