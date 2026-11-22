class Numbers(list[int]):
    pass


def source(xs: Numbers) -> Numbers:
    print("make", list(xs))
    return xs


def item(n: int) -> int:
    if n == 3:
        raise ValueError("three")
    return n * 10


xs = Numbers([1, 2])
list.__init__(xs, (x for x in source(xs)))
print(list(xs))
xs.extend([3, 4])
list.__init__(xs, [x for x in source(xs)])
print(list(xs))
try:
    list.__init__(xs, (item(n) for n in [1, 2, 3]))
except ValueError as e:
    print(str(e), list(xs))


def values(xs: Numbers):
    yield len(xs) + 7
    yield len(xs) + 7
    raise ValueError("end")


try:
    list.__init__(xs, values(xs))
except ValueError as e:
    print(str(e), list(xs))
