# pystachy: dynamic-any
# Native int-list references keep their object, storage and item identity in Any.
from typing import Any


def expose(items: list[int]) -> Any:
    return items


def same(left: Any, right: Any) -> bool:
    return left is right


def owned() -> Any:
    item = int("12345")
    items: list[int] = [item, item]
    return items


class Holder:
    def __init__(self, items: list[int]) -> None:
        self.items = items


def run() -> None:
    first = int("1000")
    equal = int("1000")
    last = int("2000")
    items: list[int] = [first, equal]
    alias = items
    value: Any = expose(items)
    holder: Any = Holder(items)
    print("object", value is alias, id(value) == id(expose(alias)), holder.items is value)
    print("type", type(value) is list, isinstance(value, list), bool(value))
    print("items", value[0] is first, value[0] is value[0], value[0] is value[1])
    restored: list[int] = value
    print("roundtrip", restored is items)
    try:
        value[99] = "not reached"
    except IndexError:
        print("index error precedes store check", items)

    value.append(last)
    alias.insert(1, last)
    value[0] = equal
    print("both views", items, value, same(items[0], equal), value[1] is last)
    if isinstance(value, list):
        value.insert(0, first)
        print("narrowed", value[0] is first)
    value.extend([first, last])
    value[1:3] = [equal, first, last]
    value[::2] = [first, equal, first, equal]
    print("slice stores", items)
    print("pop", value.pop() is last)
    del value[1]
    del value[1:3]
    value += [last]
    value *= 2
    print("inplace", value is items, items)
    value.reverse()
    value.sort()
    print("ordered", value, value.count(1000.0), value.index(2000.0), True in value)
    value.remove(2000.0)
    print("remove", items)
    print("compare", value == items, items == value, value < [9000])

    # Fresh dynamic results have boxed storage and can accept another type.
    copied: Any = value.copy()
    sliced: Any = value[::-1]
    built: Any = list(value)
    joined: Any = value + [last]
    repeated: Any = value * 2
    for fresh in [copied, sliced, built, joined, repeated]:
        fresh.append("free")
        print("fresh", fresh is value, fresh[-1], len(fresh))
    print("copy identity", copied[0] is value[0], sliced[-2] is value[0])

    value.clear()
    alias.extend([first, equal])
    iterator = iter(value)
    print("iter first", next(iterator) is first)
    alias.append(last)
    print("iter live", next(iterator) is equal, next(iterator) is last)
    print("iter exhausted", next(iterator, None))
    print("reverse iteration", list(reversed(value)))
    value.extend(value)
    print("self extend", items, value[0] is value[3])
    value *= 0
    print("empty", items, bool(value), value is alias)
    alias.extend([first, last])
    boxed_items: list[Any] = []
    boxed_items.extend(value)
    print("typed boxed extend", boxed_items, boxed_items[0] is first, items)
    native_items: list[int] = []
    boxed_source: Any = [first, last]
    native_items.extend(boxed_source)
    print("typed native extend", native_items, same(native_items[0], first))

    # Existing boxed lists remain unrestricted, including after a list test.
    unrestricted: Any = [1, 2]
    if isinstance(unrestricted, list):
        unrestricted.append("three")
    print("boxed", unrestricted)

    retained: Any = owned()
    identity = str(id(retained[0]))
    for i in range(40):
        trash: Any = [str(i), {"item": int(str(i))}]
        if len(trash) != 2:
            raise AssertionError("churn")
    print("only Any owner", retained, str(id(retained[0])) == identity, retained[0] is retained[1])


run()
