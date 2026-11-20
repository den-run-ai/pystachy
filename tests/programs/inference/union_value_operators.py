# Arithmetic, orderings, membership and conversions on closed value unions: the operation of
# the member that the value holds, and CPython's TypeError for a pair of types that has none.
from __future__ import annotations

import json

type Value = None | bool | int | float | str | list[Value] | dict[str, Value]

KEYS = ["int", "float", "bool", "none", "str", "list", "dict"]


def binary(doc: json.JSONValue) -> None:
    for key in KEYS:
        v = doc[key]
        for op in ["+1", "1+", "-1.5", "*2", "2*", "/2", "//2", "%2", "+'s'", "'s'+", "+[9]", "neg", "pos"]:
            try:
                if op == "+1":
                    print(key, op, v + 1)
                elif op == "1+":
                    print(key, op, 1 + v)
                elif op == "-1.5":
                    print(key, op, v - 1.5)
                elif op == "*2":
                    print(key, op, v * 2)
                elif op == "2*":
                    print(key, op, 2 * v)
                elif op == "/2":
                    print(key, op, v / 2)
                elif op == "//2":
                    print(key, op, v // 2)
                elif op == "%2":
                    print(key, op, v % 2)
                elif op == "+'s'":
                    print(key, op, v + "s")
                elif op == "'s'+":
                    print(key, op, "s" + v)
                elif op == "+[9]":
                    print(key, op, v + doc["list"])
                elif op == "neg":
                    print(key, op, -v)
                else:
                    print(key, op, +v)
            except TypeError as e:
                print(key, op, "TypeError", e)


def pairs(doc: json.JSONValue) -> None:
    for a in KEYS:
        for b in KEYS:
            x = doc[a]
            y = doc[b]
            try:
                print(a, "+", b, x + y)
            except TypeError as e:
                print(a, "+", b, "TypeError", e)
            z = scalar(y)
            try:
                print(a, "<", b, x < z, z >= x)
            except TypeError as e:
                print(a, "<", b, "TypeError", e)
            print(a, "==", b, x == y, x != y)


def scalar(v: json.JSONValue) -> int | float | str | None:
    # (two values that may both be lists have no compiled ordering: one side is a scalar's)
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        return v
    return None


def orderings(doc: json.JSONValue) -> None:
    for key in KEYS:
        v = doc[key]
        try:
            print(key, "< 3", v < 3, v <= 3, v > 3, v >= 3, 3 < v)
        except TypeError as e:
            print(key, "< 3 TypeError", e)
        try:
            print(key, "< 2.5", v < 2.5, 2.5 >= v)
        except TypeError as e:
            print(key, "< 2.5 TypeError", e)
        try:
            print(key, "< 'm'", v < "m", "m" < v)
        except TypeError as e:
            print(key, "< 'm' TypeError", e)


def membership(doc: json.JSONValue) -> None:
    for key in KEYS:
        v = doc[key]
        try:
            print(key, "'a' in", "a" in v, "zz" in v, "a" not in v)
        except TypeError as e:
            print(key, "'a' in TypeError", e)
        try:
            print(key, "2 in", 2 in v, 2 not in v, 9 in v)
        except TypeError as e:
            print(key, "2 in TypeError", e)
        for other in ["int", "str", "none"]:
            try:
                print(key, other, "in", doc[other] in v)
            except TypeError as e:
                print(key, other, "in TypeError", e)


def conversions(doc: json.JSONValue) -> None:
    for key in KEYS + ["digits", "char", "neg"]:
        v = doc[key]
        for name in ["int", "float", "abs", "round", "round1", "ord", "chr", "str", "bool"]:
            try:
                if name == "int":
                    print(key, name, int(v))
                elif name == "float":
                    print(key, name, float(v))
                elif name == "abs":
                    print(key, name, abs(v))
                elif name == "round":
                    print(key, name, round(v))
                elif name == "round1":
                    print(key, name, round(v, 1))
                elif name == "ord":
                    print(key, name, ord(v))
                elif name == "chr":
                    print(key, name, chr(v))
                elif name == "str":
                    print(key, name, str(v), repr(v))
                else:
                    print(key, name, bool(v))
            except (TypeError, ValueError) as e:
                print(key, name, type(e).__name__, e)


def flows(doc: json.JSONValue) -> None:
    # a result is a union value again; a total takes it
    total = 0
    for row in doc["rows"]:
        total = total + row["n"]
    print("total", total, total * 2, total > 5)
    count = 0
    for row in doc["rows"]:
        count += int(row["n"])
    print("count", count, sum(int(r["n"]) for r in doc["rows"]))
    label = ""
    for row in doc["rows"]:
        label += row["s"]
    print("label", label, len(label))
    try:
        print(doc["int"] / doc["zero"])
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    own: Value = [1, 2.5]
    print(own[0] + own[1], own[1] > 1, 1 in own, own * 2)
    small = pick(True)
    print(small + "!", small * 2, small < "z")
    try:
        print(pick(False) + "!")
    except TypeError as e:
        print("TypeError", e)
    print(pick(False) + 1, pick(False) < 9)


def pick(text: bool) -> int | str:
    if text:
        return "pq"
    return 7


def main() -> None:
    doc = json.loads('{"int": 2, "float": 2.5, "bool": true, "none": null, "str": "a", "list": [1, 2, "a"], '
                     '"dict": {"a": 1, "b": 2}, "digits": "42", "char": "x", "neg": -7, "zero": 0, '
                     '"rows": [{"n": 1, "s": "a"}, {"n": 2.5, "s": "b"}, {"n": 4, "s": "c"}]}')
    binary(doc)
    pairs(doc)
    orderings(doc)
    membership(doc)
    conversions(doc)
    flows(doc)


main()
