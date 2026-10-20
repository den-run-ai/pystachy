# dict() of tuples of another length than 2 (#524): an empty list (of a variable, zip(), a
# comprehension) makes an empty dict, of the type the context wants; one with an item raises
# CPython's ValueError where it runs, which an except clause catches, after the output before it.
xs: list[tuple[int, int, int]] = []
print(dict(xs), len(dict(xs)), dict(xs) == {})
e: dict[str, int] = dict(xs)
e["b"] = 2
print(e)
ones: list[tuple[str]] = []
no: list[int] = []
print(dict(ones), dict(zip(no, no, no)), dict(zip("ab", no)))
print(dict([(x, x, x) for x in range(0)]), dict([(x,) for x in ""]))
for k in dict(xs):
    print(k)
try:
    xs.append((1, 2, 3))
    print(dict(xs))
except ValueError as ex:
    print("ValueError:", ex)
try:
    print(dict(zip("ab", "cd", "ef")))
except ValueError as ex:
    print("ValueError:", ex)
try:
    print(dict([(x,) for x in "abc"]))
except ValueError as ex:
    print("ValueError:", ex)
try:
    print(dict(((1, 2, 3, 4),)))
except ValueError as ex:
    print("ValueError:", ex)


# an iterator (a generator expression, map(), filter(), zip(), reversed()) is taken only up to
# its first item, which raises: no later one is made
def made(x: int) -> int:
    print("made", x)
    return x


def three(x: int) -> tuple[int, int, int]:
    if x > 1:
        raise KeyError(x)
    return (x, x, x)


def keep(t: tuple[int, int, int]) -> bool:
    print("keep", t)
    return t[0] > 1


trips = [(1, 2, 3), (4, 5, 6), (7, 8, 9)]
try:
    print(dict((made(x), x, x) for x in range(3)))
except ValueError as ex:
    print("ValueError:", ex)
try:
    print(dict((1 // (1 - x), x, x) for x in range(3)))
except ValueError as ex:
    print("ValueError:", ex)
except ZeroDivisionError as ex:
    print("ZeroDivisionError:", ex)
try:
    print(dict(map(three, [1, 2, 3])))
except ValueError as ex:
    print("ValueError:", ex)
except KeyError as ex:
    print("KeyError:", ex)
try:
    print(dict(three(made(x)) for x in range(3)))
except ValueError as ex:
    print("ValueError:", ex)
except KeyError as ex:
    print("KeyError:", ex)
try:
    print(dict(filter(keep, trips)))
except ValueError as ex:
    print("ValueError:", ex)
try:
    print(dict((x, x, x) for x in range(5) if made(x) > 1))
except ValueError as ex:
    print("ValueError:", ex)
try:
    print(dict(() for x in range(3) if made(x) > 0))
except ValueError as ex:
    print("ValueError:", ex)
try:
    print(dict(reversed(trips)))
except ValueError as ex:
    print("ValueError:", ex)
print(dict((made(x), x, x) for x in range(0)), dict(map(three, no)), dict(filter(keep, trips[:0])))
print(dict(reversed(trips[:0])), dict((x,) for x in "abc" if made(len(x)) > 1))
u: dict[str, int] | list[int] = dict(trips[:0])
a: dict[str, int] = dict([(x, x, x) for x in "ab" if x > "z"])
b: dict[str, int] = dict(zip(no, no, no))
print(u, a, b)
try:
    c: dict[str, int] = dict([("a", 1, 2)])
    print(c)
except ValueError as ex:
    print("ValueError:", ex)
print("before")
print(dict([(1, 2, 3)]))
