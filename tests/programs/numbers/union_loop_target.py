# A for loop whose target is an int | float local assigns it each int item, so that after the
# loop it holds the last item, or the float it held where there was none (#1551).
def literal() -> str:
    c: int | float = 0.0
    for c in [1, 2]:
        pass
    return str(c)


def last(items: list[int]) -> str:
    c: int | float = 0.0
    for c in items:
        pass
    return str(c)


def total(items: list[int]) -> str:
    c: int | float = 0.5
    s = 0.0
    for c in items:
        s += c
    return str(s) + " " + str(c)


print(literal())
print(last([1, 2]))
print(last([]))
print(total([1, 2, 3]))
