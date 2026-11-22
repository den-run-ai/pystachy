# In-place operators through closed value unions: x op= y and o[k] op= y select the operation of
# the members their values hold. A list on the left of += or *= changes in place, so another
# reference to it sees the change, as in CPython; o and k are evaluated once.
from __future__ import annotations

import json

KEYS = ["int", "float", "bool", "none", "str", "list", "dict"]


def fresh() -> json.JSONValue:
    return json.loads('{"int": 2, "float": 2.5, "bool": true, "none": null, "str": "ab", "list": [1, "x"], "dict": {"k": 1, "j": 2}}')


def noisy(tag: str, v: int) -> int:
    print("eval", tag)
    return v


def rem(v: json.JSONValue, n: int | None) -> None:
    try:
        print(v % n)
    except TypeError as e:
        print("TypeError", e)
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)


def items() -> None:
    doc = json.loads('{"count": 1, "rows": [[1, 2], [3]], "name": "ab", "ratio": 0.5}')
    doc["count"] += 1
    doc["count"] *= 2.5
    doc["name"] += "cd"
    doc["rows"][noisy("index", 1)] *= noisy("factor", 2)
    print(doc)
    rows = doc["rows"]
    first = rows[0]
    first += [9]
    rows += [[7]]
    print(doc["rows"], first)
    try:
        doc["ratio"] += "x"
    except TypeError as e:
        print("TypeError", e)
    try:
        doc["rows"] += 5
    except TypeError as e:
        print("TypeError", e)
    try:
        doc["rows"] *= 1.5
    except TypeError as e:
        print("TypeError", e)
    try:
        doc["missing"] += 1
    except KeyError as e:
        print("KeyError", e)
    n = doc["count"]
    n -= 1
    n //= 2
    print(n, doc["count"], -n, +n, abs(n), not n, n == 2, n != 2.0)


def pairs() -> None:
    for a in KEYS:
        for b in KEYS:
            doc = fresh()
            x = doc[a]
            alias = x
            y = doc[b]
            try:
                x += y
                print(a, "+=", b, x, alias, doc[a])
            except TypeError as e:
                print(a, "+=", b, "TypeError", e)
            doc = fresh()
            x = doc[a]
            alias = x
            y = doc[b]
            try:
                x *= y
                print(a, "*=", b, x, alias, doc[a])
            except TypeError as e:
                print(a, "*=", b, "TypeError", e)
    doc = fresh()
    rows = doc["list"]
    rows += rows
    rows += "cd"
    rows += {"k": 1}
    rows *= True
    print(rows, doc["list"])
    text = doc["str"]
    text += "!"
    text *= 2
    print(text, doc["str"])


def remainders() -> None:
    doc = json.loads('{"i": 7, "f": 7.5, "s": "plain", "n": null, "l": [1], "b": true}')
    for key in ["i", "f", "s", "n", "l", "b"]:
        for n in [3, None, 0]:
            rem(doc[key], n)


items()
pairs()
remainders()
