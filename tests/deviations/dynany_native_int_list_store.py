# pystachy: dynamic-any
# Newly supported native int-list aliases check dynamic stores. CPython ignores
# their annotations and accepts every incompatible value below.
import copy
from typing import Any


def run() -> None:
    for operation in range(10):
        items: list[int] = [1, 2, 3]
        value: Any = items
        try:
            if operation == 0:
                value.append("bad")
            elif operation == 1:
                value.insert(1, "bad")
            elif operation == 2:
                value[1] = "bad"
            elif operation == 3:
                value.extend([4, "bad", 5])
            elif operation == 4:
                value += [4, "bad", 5]
            elif operation == 5:
                value[1:2] = [4, "bad", 5]
            elif operation == 6:
                value[::2] = [4, "bad"]
            elif operation == 7:
                value.append(True)
            elif operation == 8:
                if isinstance(value, list):
                    value.append(1.0)
            else:
                value[1:2] += ["bad"]
        except TypeError:
            print("blocked", operation, items, value is items)
        else:
            print("unchecked", operation, items)

    items = [1, 2]
    value = items
    # A Python list tag does not prove boxed-item storage. Do not reinterpret
    # the native data through a different concrete annotation.
    try:
        boxed: list[Any] = value
        boxed.append("bad")
    except TypeError:
        print("boxed layout rejected", items)
    unrestricted: Any = [1, 2]
    try:
        narrowed: list[int] = unrestricted
        narrowed.append(3)
    except TypeError:
        print("late constraint rejected")
    unrestricted.append("free")
    print("still unrestricted", unrestricted)
    mixed: Any = [3, "bad", 4]
    try:
        items.extend(mixed)
    except TypeError:
        print("typed extend prefix", items)
    try:
        items += mixed
    except TypeError:
        print("typed inplace prefix", items)
    try:
        items[1:2] = mixed
    except TypeError:
        print("typed slice unchanged", items)


run()


class CopyPair:
    def __init__(self, values: list[int]):
        self.dynamic: Any = values
        self.native = values


original: list[int] = [1, 2]
cloned = copy.deepcopy(CopyPair(original))
print("deepcopy shared", cloned.dynamic is cloned.native, cloned.native is not original)
try:
    cloned.dynamic.extend([4, "bad", 5])
except TypeError:
    print("deepcopy prefix", cloned.native, original)
try:
    cloned.dynamic[0:1] = ["bad"]
except TypeError:
    print("deepcopy slice", cloned.native)
try:
    copied_boxes: list[Any] = cloned.dynamic
    copied_boxes.append("bad")
except TypeError:
    print("deepcopy boxed layout rejected", cloned.native)
