# pystachy: python-int
# pystachy: dynamic-any
# Cross-layout dictionary equality keeps wide keys, Python hashes and callbacks.
from typing import Any

wide = 2 ** 70
native: dict[int, int] = {wide: 7, -wide: 9}
boxed: dict[Any, Any] = {wide: 7, -wide: 9}
print(native == boxed, boxed == native, native != boxed)
floating: dict[Any, Any] = {float(wide): 7, float(-wide): 9}
print(native == floating, floating == native)
different: dict[Any, Any] = {wide + 1: 7, -wide: 9}
print(native == different, different == native)
values: dict[Any, int] = {wide: 7, -wide: 9}
print(native == values, values == native)
print(native.copy() == boxed, dict.fromkeys([wide, -wide], 7) == {wide: 7, -wide: 7})

# The native sentinel and a different wide key can have the same Python hash.
# Native queries must never mistake that sentinel for the small integer itself.
small = -2 ** 63
collision = -16 * (2 ** 61 - 1) - 4
print(hash(small), hash(collision))
colliding: dict[int, int] = {collision: 1, small: 2, 0: 3}
print(len(colliding), colliding[collision], colliding[small], colliding[0])
print(colliding.get(collision), colliding.get(small), colliding.setdefault(small, 8))
colliding_boxed: dict[Any, Any] = {collision: 1, small: 2, 0: 3}
print(colliding == colliding_boxed, colliding_boxed == colliding)
print(colliding.pop(small), len(colliding), collision in colliding, small in colliding)
colliding[small] = 5
print(colliding.pop(collision), colliding[small], len(colliding))


class Key:
    def __init__(self, value: Any):
        self.value = value

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: Any) -> bool:
        global action
        print('key', other)
        current = action
        action = 0
        if current == 1:
            typed.clear()
        elif current == 2:
            dynamic.clear()
        elif current == 3:
            del typed[wide]
            typed[wide] = 2
        elif current == 4:
            raise ValueError('wide key callback')
        return self.value == other


typed: dict[int, int] = {}
dynamic: dict[Any, int] = {}
action = 0
for reverse in [False, True]:
    for case in range(5):
        typed = {wide: 1}
        dynamic = {Key(wide): 1}
        action = case
        print('case', reverse, case)
        try:
            print(dynamic == typed if reverse else typed == dynamic)
        except ValueError as error:
            print(error)
        print(len(typed), len(dynamic))

# Tuple-key callbacks must read the tuples' promoting storage layout too.
action = 0
tuple_left = {(Key(wide), wide): 8}
tuple_right = {(wide, wide): 8}
print(tuple_left == tuple_right, tuple_right == tuple_left)
nested_left = {((wide, 7), Key(wide)): 9}
nested_right = {((wide, 7), wide): 9}
print(nested_left == nested_right, nested_right == nested_left)
