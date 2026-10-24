# pystachy: dynamic-any
# a comparison's other operand only hints at the type of keys() of a dict whose keys are Any
# values, which keys() does not unbox to it: unboxing raised TypeError for an int key, where
# CPython compares (#830). Paired list iteration retains each item's actual type.
from typing import Any

d: dict[Any, Any] = {1: "x"}
print(["1"] == d.keys())
