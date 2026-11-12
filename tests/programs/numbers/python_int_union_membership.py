# pystachy: python-int
# A tuple's int is a promoting int here, and a closed union holds a 64-bit int. They were
# taken for values of types that are never equal, so 1 in (1, "a") was False for a union
# holding 1. An item that fits 64 bits now compares with what the union holds; one past
# 64 bits equals no int a union can hold.
import json


def has(key: int | str | None, mixed: tuple[str, int, float]) -> list[bool]:
    return [key in mixed, key not in mixed, mixed.count(1) == 1, mixed[1] in (key, "z")]


def other(value: "json.JSONValue", label: str | list[int], mixed: "tuple[str, int, float, None, list[int]]", big: tuple[int, str]) -> list[bool]:
    return [value in mixed, label in mixed, value in big, value not in big, label in big, big[0] in (value, label), value in (2**70, "one")]


def member(key: int | str | None, pair: tuple[int, str]) -> list[bool]:
    return [key in pair, key not in pair]


for key in [1, "one", None, 2, "x", 2**62, -(2**63), 0]:
    print(repr(key), has(key, ("one", 1, 2.5)), has(key, ("x", 2**62, 1.0)), has(key, ("", -(2**63), 0.0)))
VALUES: "list[json.JSONValue]" = [1, 1.0, True, "one", None, [1], 2.5, 0, 2**62, {"a": 1}, False]
for value in VALUES:
    print(repr(value), other(value, "one", ("one", 1, 2.5, None, [1]), (2**80, "one")), other(value, [1], ("a", 2**62, 1.0, None, [2]), (1, "b")))
print(member(1, (1, "a")), member(1, (2**80, "a")), member("a", (2**80, "a")), member(None, (2**80, "a")), member(2**63 - 1, (2**63 - 1, "")))
