# pystachy: dynamic-any
# x if c else x, and x := x: the one binding of x either way, whose object the value keeps where
# it becomes an Any value, as CPython's names hold one object (#807)
from typing import Any
import sys

x = int("1000")
a: Any = x
flag = bool(int("1"))
y = x if flag else x
b: Any = y
print(a is b, id(a) == id(b))
z = int("3000")
ys: list[Any] = [z, (z := z)]
print(ys[0] is ys[1], id(ys[0]) == id(ys[1]))


def local(f: bool) -> None:
    p = int("4000")
    c: Any = p
    q = p if f else p
    d: Any = q
    w = int("5000")
    ws: list[Any] = [w, (w := w)]
    print(c is d, id(c) == id(d), ws[0] is ws[1])


local(True)
local(False)

# Global reads carry snapshots instead of mutable slots. A conditional keeps the
# selected snapshot, also for equal-but-distinct values and nested selections.
other = int("1000")
first_float = float("-0.0")
other_float = float("-0.0")
for choose in [False, True]:
    picked = x if choose else other
    expected: Any = x if choose else other
    actual: Any = picked
    print("selected int", actual is expected, id(actual) == id(expected))
    other_box: Any = other if choose else x
    print("unselected int", actual is other_box)
    picked_float = first_float if choose else other_float
    expected_float: Any = first_float if choose else other_float
    actual_float: Any = picked_float
    print("selected float", actual_float is expected_float, id(actual_float) == id(expected_float))
    nested = (x if choose else other) if choose else (other if choose else x)
    nested_box: Any = nested
    current_x: Any = x
    print("nested selection", nested_box is current_x)


def replace() -> bool:
    global x
    print("replace")
    x = int("1000")
    return True


for choose in [False, True]:
    saved: Any = x
    effect_choice = (x if replace() else x) if choose else other
    effect_box: Any = effect_choice
    effect_expected: Any = x if choose else other
    print("effecting arm", effect_box is effect_expected, effect_box is saved)


# Only the live predecessor contributes a snapshot when the other arm terminates.
live = bool(int("1"))
left = x if live else sys.exit(1)
right = sys.exit(1) if not live else x
left_box: Any = left
right_box: Any = right
current: Any = x
print("terminating arms", left_box is current, right_box is current)
