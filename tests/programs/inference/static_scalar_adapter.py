# pystachy: dynamic-any
from typing import Any
from checked_scalar import classify, float_result


def boxed(value: Any) -> Any:
    return value


for item in ["hello", 2.5, True, False, 1, None, [1]]:
    print(classify(boxed(item)))
print(classify("concrete"), classify(3))
nan = boxed(float("nan"))
print(float_result(nan) is nan)
