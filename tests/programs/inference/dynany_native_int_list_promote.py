# pystachy: dynamic-any
# pystachy: python-int
# Wide integer storage and its item boxes survive with only an Any owner.
from typing import Any


def same(left: Any, right: Any) -> bool:
    return left is right


def make() -> Any:
    first = int("9223372036854775808")
    equal = int("9223372036854775808")
    items: list[int] = [first, equal]
    value: Any = items
    print("wide identity", value[0] is first, value[1] is equal, value[0] is value[1])
    value.append(first)
    print("wide write", same(items[-1], first))
    return value


def churn() -> None:
    for i in range(40):
        trash: Any = [str(i), {"item": int(str(i))}]
        if len(trash) != 2:
            raise AssertionError("churn")


def run() -> None:
    value: Any = make()
    retained = str(id(value[0]))
    churn()
    items: list[int] = value
    print("retained", value, str(id(value[0])) == retained, items is value)
    number = int("18446744073709551616")
    value.insert(1, number)
    value[0] = number
    value.extend([number])
    value[1:2] = [number, number]
    print("wide mutations", items, same(items[0], number), value[2] is number)
    popped: Any = value.pop()
    value.clear()
    items.append(number)
    churn()
    print("refill", value[0] is number, popped is number, value)
    copied: Any = value.copy()
    copied.append("free")
    print("wide copy", copied, copied[0] is number)


run()
