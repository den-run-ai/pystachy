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


def lookup(values: dict[str, int], key: str) -> int:
    found = values.get(key)
    if found is None:
        return -1
    return found + 7


def total(xs: list[int]) -> int:
    value: int | None = None
    result = 0
    for x in xs:
        value = None if x < 0 else x
        result += 23 if value is None else value
    return result


def drain(it) -> list[int]:
    out: list[int] = []
    while True:
        x = next(it, None)
        if x is None:
            break
        out.append(x)
    return out


print(accumulate(5), accumulate(4), maybe(True, 7), maybe(False, 7))
print(describe(bump(3)), describe(bump(2.5)), describe(accumulate(3)))
print(lookup({"a": 1}, "a"), lookup({"a": 1}, "b"), total([1, -2, 3]), drain(iter([5, 6])))
