# A closed union of builtin values against a str or a number: only the union's str can equal a
# str, and only its int, float or bool a number, so == and != test the tag and compare that
# member, and in, index() and count() of a tuple do the same for each item. The generic walk
# they replace (pys_eq over descriptors, the scalar boxed first) must agree for every pair,
# including None, NaN, bool against int and float, containers and ints near 2**62.
import json


def kind(value: "json.JSONValue") -> str:
    if value == "write":
        return "write"
    if value != "read" and value == 1:
        return "one"
    if 2.5 == value:
        return "float"
    if value == True:
        return "true"
    return "other"


def scalar(value: int | float | str, other: bool | str | None) -> list[bool]:
    return [value == "x", value == 1, value == 1.0, value == True, "x" != value, other == "x", other == 1, other != 0, 0 == other, value == 0.5]


def miss(value: int | float, flag: "list[int] | dict[str, int]") -> list[bool]:
    return [value == "1", "1" != value, flag == "x", flag != 1]


VALUES: "list[json.JSONValue]" = ["write", "read", 1, 1.0, True, False, 2.5, None, [], {}, ["write"], {"write": 1}, 0, float("nan"), "", 2**62, -1]
for v in VALUES:
    print(repr(v), kind(v))
for a in [1, 1.0, "x", 0, 0.5, float("nan"), "1"]:
    for b in [True, False, "x", None, ""]:
        print(repr(a), repr(b), scalar(a, b))
print(miss(1, [1]), miss(1.0, {"x": 1}))
names = ("write", "edit")
for v in VALUES:
    print(v in names, v not in names, v in ["write", 1, None], v in (1, 2.5), end=" | ")
print()


def member(value: "json.JSONValue", key: int | str | None, mixed: "tuple[str, int, float, None, list[int]]") -> list[bool]:
    return [value in ("write", "edit"), value not in ("a",), value in (1, "one", 2.5, True), key in ("x", 1), key in (1.0, "1"), mixed.count(1) == 1, "one" in (value, key)]


def find(items: "list[json.JSONValue]", pairs: "tuple[int | str, str | None, json.JSONValue]") -> list[int]:
    out: list[int] = []
    for needle in ("write", "x"):
        out.append(items.index(needle) if needle in items else -1)
        out.append(items.count(needle))
        out.append(pairs.count(needle))
    out.append(pairs.index(1) if 1 in pairs else -1)
    out.append(items.count(1))
    out.append(items.count(2.5) + items.count(True) + items.count(0))
    return out


for v in VALUES:
    for k in [1, "x", None, "1", 0]:
        print(member(v, k, ("one", 1, 2.5, None, [1])), end=" ")
    print()
print(find(["write", 1, True, 1.0, None, "x", "write", 2.5, 0, False], (1, "x", "write")))
print(find([], ("x", None, 1)))
