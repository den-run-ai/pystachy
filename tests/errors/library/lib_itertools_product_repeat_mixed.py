# error: unsupported operand types for +: list[list[int]] and list[list[str]] (a list holds items of one type) (compiling itertools._pools(
# itertools.product() with repeat yields tuples whose length the program knows only as it runs,
# whose items have one type; without repeat, each iterable's items keep their type
# (lib/compatibility.md)
from itertools import product

print(list(product([1, 2], ["a"], repeat=2)))
