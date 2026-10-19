"""Recursive container slots preserve their original pointer and shared mutations."""
type Value = None | bool | int | float | str | list[Value] | dict[str, Value]


def main() -> None:
    items: list[Value] = [1, "x", None]
    value: Value = items
    if isinstance(value, list):
        print(value is items)
        value.append({"nested": [False]})
        value[0] = "changed"
    print(items)
    print(None in items, 1 in items, "changed" in items)
    copied: list[Value] = [item for item in items]
    print(copied == items, copied is items)
    mapping: dict[str, Value] = {"items": items}
    selected = mapping.get("items")
    if isinstance(selected, list):
        selected.append(2.5)
    print(items[-1], mapping.get("missing"))
    popped = mapping.pop("items")
    if isinstance(popped, list):
        print(popped is items, len(popped))
    mapping["again"] = [True]
    for key, item in mapping.items():
        if isinstance(item, list):
            print(key, len(item))
    cycle: list[Value] = []
    cycle.append(cycle)
    print(cycle, cycle == cycle)
    numbers: list[Value] = [1, 2]
    print(numbers == [1.0, 2.0])
    nested: list[Value] = [[1], {"x": [True]}]
    print([1.0] in nested, nested.count([1.0]), nested.index([1]))
    nested.remove([1.0])
    print(nested)


main()

