# error: cannot compare list[str] == list[dyn]
# pystachy: dynamic-any
# a comparison's other operand only hints at the type of keys() of a dict whose keys are Any
# values, which keys() does not unbox to it: unboxing raised TypeError for an int key, where
# CPython compares (#830); the comparison is rejected at compile time, as before #829
from typing import Any

d: dict[Any, Any] = {1: "x"}
print(["1"] == d.keys())
