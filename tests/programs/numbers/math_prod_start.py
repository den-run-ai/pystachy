# math.prod(iterable, start=s) multiplies s by each item in turn (PyNumber_Multiply), so a str or
# list start is repeated by int items, one product at a time (an item below 1 empties it, and it
# stays empty), and an empty iterable returns the start itself, also a dict or a set; a start
# that the first item cannot multiply raises CPython's TypeError (#325).
from math import prod

print(prod([2, 3], start="ab"), prod([2, -1, 3], start=[1]), prod([3], start=[1, 2]), repr(prod([0, 5], start="x")))
print(prod([True, True], start="x"), prod([False], start=[7]), prod(range(1, 4), start="é"), prod((2, 2), start=["日"]))
e: list[int] = []
lst = [1, 2]
print(prod(e, start={2: 3}), prod(e, start="ab"), prod(e, start=lst) is lst, prod([1], start=lst) is lst, prod(e, start={1, 2}))
print(prod((n for n in [2, 3]), start="-"), prod([n + 1 for n in range(3)], start="o"))
for xs in [[1], [2, 3]]:
    try:
        print(prod(xs, start={2: 3}))
    except TypeError as ex:
        print("TypeError", ex)
    try:
        print(prod(xs, start={"s"}))
    except TypeError as ex:
        print("TypeError", ex)
fs: list[float] = []
print(prod(fs, start="ab"), prod(fs, start=[0]))
try:
    print(prod([1.5], start="ab"))
except TypeError as ex:
    print("TypeError", ex)
try:
    print(prod(["x"], start=[1]))
except TypeError as ex:
    print("TypeError", ex)


# the iterable's items are taken once start is evaluated
def items(tag: str) -> list[int]:
    print("eval", tag, end="; ")
    return [2, 2]


def start(tag: str) -> str:
    print("eval", tag, end="; ")
    return "ab"


def item(n: int) -> int:
    print("item", n, end="; ")
    return n


print(prod(items("iterable"), start=start("start")))
print(prod((item(n) for n in [1, 3]), start=start("start")))
