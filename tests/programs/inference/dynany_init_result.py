# pystachy: dynamic-any
# A constructor checks the returned Any value's type, not its truthiness.
from typing import Any


class Result:
    def __init__(self, n: int) -> Any:
        if n == 1:
            return 0
        if n == 2:
            return ""
        return None


for n in [0, 1, 2]:
    try:
        Result(n)
        print("made", n)
    except TypeError as e:
        print("TypeError", e)

r = Result(0)
print("explicit", r.__init__(1), repr(r.__init__(2)))
