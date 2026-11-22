# Loops over closed value unions: the list, dict or str that the value holds is stepped through
# as that type's own loop steps through it; None and numbers raise CPython's TypeError.
from __future__ import annotations

import json
from typing import Iterator

type Value = None | bool | int | float | str | list[Value] | dict[str, Value]


def show(tag: str, v: json.JSONValue) -> None:
    try:
        out: list[str] = []
        for x in v:
            out.append(repr(x))
        print(tag, "items", out)
    except TypeError as e:
        print(tag, "TypeError", e)


def pick(text: bool) -> int | str:
    if text:
        return "pq"
    return 7


def gen() -> Iterator[int]:
    print("gen starts")
    yield 1


def main() -> None:
    doc = json.loads('{"rows": [{"id": 1, "name": "ab", "tags": ["x", "y"]}, {"id": 2.5, "name": "", "tags": []}], '
                     '"count": 2, "ok": true, "none": null, "ratio": 0.5, "text": "héé", "empty": [], "nested": [[1, 2], [3], []]}')
    for key in ["rows", "count", "ok", "none", "ratio", "text", "empty", "nested"]:
        show(key, doc[key])
    show("doc", doc)

    # the loop's variable is a union value again: indexes, len(), nested loops
    for row in doc["rows"]:
        print(row["id"], len(row["tags"]), [t for t in row["tags"]])
        for tag in row["tags"]:
            print(" tag", tag, len(tag))
        for ch in row["name"]:
            print(" ch", ch)
    total = 0
    for group in doc["nested"]:
        for n in group:
            if isinstance(n, int):
                total += n
    print("total", total)

    # enumerate, zip, break, continue, else
    for i, row in enumerate(doc["rows"]):
        print("enum", i, row["id"])
    for i, ch in enumerate(doc["text"], 10):
        print("enum start", i, ch)
    for a, b in zip(doc["rows"], doc["text"]):
        print("zip", a["id"], b)
    for num, grp in zip([10, 20, 30], doc["nested"]):
        print("zip list", num, grp)
    for k in doc:
        if k == "count":
            continue
        if k == "none":
            break
        print("key", k)
    else:
        print("no break")
    for x in doc["empty"]:
        print("never")
    else:
        print("empty else")

    # comprehensions and generator expressions
    print([len(r["tags"]) for r in doc["rows"]])
    print({str(k): len(k) for k in doc["rows"][0]})
    print(sorted({str(c) for c in doc["text"]}))
    print(",".join(c.upper() for c in doc["text"]), any(len(g) == 0 for g in doc["nested"]), all(len(g) > 0 for g in doc["nested"]))
    print([[n for n in g] for g in doc["nested"]])

    # a list that grows during its loop is stepped through to its new end, as a list's loop is
    grow = json.loads('[1, 2, 3]')
    seen = 0
    for x in grow:
        seen += 1
        if seen < 3 and isinstance(grow, list):
            grow.append(seen)
    print("grow", seen, grow)
    # a dict that changes size during its loop raises, as a dict's loop does
    table = json.loads('{"a": 1, "b": 2}')
    try:
        for k in table:
            if isinstance(table, dict):
                table[k + "x"] = 0
        print("no error")
    except RuntimeError as e:
        print("RuntimeError", e)

    # a number raises where the loop starts: the generator beside it in zip() has given no item
    try:
        for first, second in zip(gen(), doc["count"]):
            print("never", first, second)
    except TypeError as e:
        print("zip TypeError", e)

    # dict views of a union's dict; another member has no such method
    for k, v in doc["rows"][0].items():
        print("item", k, v)
    for k in doc["rows"][1].keys():
        print("key", k)
    for v in doc["rows"][0].values():
        print("value", v)
    for what in ["count", "rows", "text", "none"]:
        try:
            for k, v in doc[what].items():
                print("never")
        except AttributeError as e:
            print("AttributeError", e)

    # a program's own alias, and a union of scalars
    own: Value = [1, "two", [3.5, None], {"k": True}]
    for item in own:
        print("own", item)
    for c in pick(True):
        print("small", c)
    try:
        for c in pick(False):
            print("never")
    except TypeError as e:
        print("small TypeError", e)


main()
