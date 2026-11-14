# pystachy: dynamic-any
# object in a return or container annotation is an Any value in a module that opts in.
from typing import cast, Any

NO = object()


def prep(n: int) -> tuple[str | None, object]:
    if n == 0:
        return None, "direct"
    if n == 1:
        return None, 5
    return "state", NO


for i in range(3):
    s, r = prep(i)
    print(s, r is NO)
x = cast("list[Any]", [1, "a"])
print(x)
