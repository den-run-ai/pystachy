# pystachy: dynamic-any
from typing import Any


def joined(xs: list[str], lo: int | None, hi: int | None) -> str:
    return "☆".join(xs[lo:hi])


items = ["first", "α", "🐍", "", "nul\x00"]
for lo, hi in [(None, -1), (-2, None), (-100, 2), (3, 1), (100, 100), (0, -9223372036854775808)]:
    print(repr(joined(items, lo, hi)))
print(repr(joined([], None, None)))


def separator() -> str:
    print("separator")
    return "+"


def start() -> int:
    global items
    items.append("last")
    items = ["replacement"]
    print("start")
    return -3


def stop() -> int:
    print("stop")
    return 99


# Hold the old list across both calls, including the mutation in start().
print(repr(separator().join(items[start():stop()])))
print(items)


def bad_bound() -> Any:
    return "bad"


try:
    print("".join(items[bad_bound():stop()]))
except TypeError as err:
    print(err)


def tail(first: int) -> str:
    # Fresh heap strings are reachable through the list's storage during result allocation.
    words = ["item-" + str(i) for i in range(80)]
    return "|".join(words[first:])


print(tail(77), len(tail(2)))
