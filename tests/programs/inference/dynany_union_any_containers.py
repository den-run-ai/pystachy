# pystachy: dynamic-any
# A union with a container of Any values among its members is an Any value.
from typing import Any

JSONReturnType = dict[str, Any] | list[Any] | str | float | int | bool | None


def pick(n: int) -> JSONReturnType:
    if n == 0:
        return {"a": 1}
    if n == 1:
        return [1, "x", None]
    if n == 2:
        return "s"
    if n == 3:
        return 1.5
    if n == 4:
        return 7
    if n == 5:
        return True
    return None


def wrap(n: int) -> list[JSONReturnType]:
    out: list[JSONReturnType] = []
    for i in range(n):
        out.append(pick(i))
    return out


def pair(n: int) -> tuple[bool, JSONReturnType]:
    return n > 2, pick(n)


obj: dict[str, JSONReturnType] = {}
for i in range(7):
    obj[str(i)] = pick(i)
print(obj)
print(wrap(7))
print(pair(3), pair(0))


def main() -> None:
    v = pick(1)
    if isinstance(v, list):
        v.append(3)
    print(v)
    w: Any = pick(0)
    w["k"] = pick(1)
    print(w)
    items: list[Any] = []
    items.append(pick(2))
    items.append(pick(0))
    print(items)
    r: JSONReturnType = items
    print(r == [pick(2), pick(0)], r == "", pick(2) == "s")


main()
