# pystachy: dynamic-any
# A display retains each numeric object before evaluating the next item's rebinding.
from typing import Any


def lists() -> None:
    x = int("1000")
    items: list[Any] = [x, x, (x := int("2000"))]
    print("list", items[0] is items[1], items[0] is items[2], items[2] is x)
    print("ids", id(items[0]) == id(items[1]), id(items[0]) == id(items[2]))
    x = int("1000")
    equal: list[Any] = [x, x, (x := int("1000"))]
    print("equal integers", equal[0] is equal[1], equal[0] is equal[2])
    y = float("1.5")
    floats: list[Any] = [y, y, (y := float("1.5"))]
    print("equal floats", floats[0] is floats[1], floats[0] is floats[2])
    z = float("-0.0")
    zeros: list[Any] = [z, z, (z := float("0.0"))]
    print("zeros", zeros[0] is zeros[1], zeros[0] is zeros[2], zeros)
    x = int("1000")
    stars: list[Any] = [x, *[True], x, (x := int("2000"))]
    print("star list", stars[0] is stars[2], stars[0] is stars[3], stars[3] is x)
    x = int("1000")
    mixed = [x, x, "marker", (x := int("2000"))]
    print("inferred mixed list", mixed[0] is mixed[1], mixed[0] is mixed[3])


def dicts() -> None:
    x = int("1000")
    values: dict[str, Any] = {"a": x, "b": x, "c": (x := int("2000"))}
    print("dict values", values["a"] is values["b"], values["a"] is values["c"], values["c"] is x)
    y = float("nan")
    keys: dict[Any, str] = {y: "first", y: "replacement", (y := float("nan")): "new"}
    print("nan keys", len(keys), list(keys.values()))
    z = float("nan")
    pairs: dict[Any, Any] = {z: z, z: (z := float("nan"))}
    for key in pairs:
        print("key precedes value", len(pairs), key is pairs[key], pairs[key] is z)


def sets() -> None:
    x = float("nan")
    items: set[Any] = {x, x, (x := float("nan"))}
    print("nan set", len(items), x in items)


lists()
dicts()
sets()
