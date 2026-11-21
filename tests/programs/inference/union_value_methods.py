# Method calls on closed value unions: the method of the str, list, dict or number that the
# value holds; another member raises CPython's AttributeError before the arguments are evaluated.
from __future__ import annotations

import json

type Value = None | bool | int | float | str | list[Value] | dict[str, Value]


def noisy(v: json.JSONValue) -> json.JSONValue:
    print("  argument evaluated")
    return v


def call(tag: str, v: json.JSONValue) -> None:
    for name in ["upper", "append", "get", "bit_length", "keys", "copy"]:
        try:
            if name == "upper":
                print(tag, name, v.upper())
            elif name == "append":
                v.append(noisy(1))
                print(tag, name, v)
            elif name == "get":
                print(tag, name, v.get("id"), v.get("zz"), v.get("zz", 5))
            elif name == "bit_length":
                print(tag, name, v.bit_length())
            elif name == "keys":
                print(tag, name, list(v.keys()))
            else:
                print(tag, name, v.copy())
        except AttributeError as e:
            print(tag, name, "AttributeError", e)


def main() -> None:
    doc = json.loads('{"rows": [{"id": 1, "name": "ab cd", "tags": ["x", "y"]}], "count": 5, "ok": true, '
                     '"none": null, "ratio": 0.5, "text": "Hello, World", "nums": [3, 1, 2]}')
    for key in ["rows", "count", "ok", "none", "ratio", "text"]:
        call(key, doc[key])
    call("row", doc["rows"][0])

    # str methods
    text = doc["text"]
    print(text.lower(), text.split(", "), text.startswith("Hell"), text.replace("l", "L"), text.find("W"), text.strip("Hd"))
    print("-".join(str(t) for t in doc["rows"][0]["tags"]), text.count("l"), text.index("o"))
    # list methods
    nums = doc["nums"]
    nums.append(4)
    nums.extend([5, "six"])
    nums.insert(0, None)
    print(nums, nums.index(4), nums.count(1), len(nums))
    print(nums.pop(), nums.pop(0), nums)
    nums.reverse()
    nums.remove(4)
    print(nums, nums.copy() == nums)
    nums.clear()
    print(nums, doc["nums"])
    # dict methods
    row = doc["rows"][0]
    print(row.get("name"), row.get("none"), row.get("none", [1]), list(row.keys()), list(row.values()), list(row.items()))
    print(row.pop("id"), row.pop("zz", "default"), row.setdefault("new", 7), row.setdefault("new", 8))
    row.update({"more": [1, 2]})
    print(row, row.copy() == row)
    try:
        row.pop("zz")
    except KeyError as e:
        print("KeyError", e)
    row.clear()
    print(row, doc["rows"])
    # number methods
    print(doc["count"].bit_length(), doc["ratio"].hex(), doc["ok"].bit_length())
    # pop() of a list or of a dict: the arguments each takes
    for what in ["rows", "nums2"]:
        d2 = json.loads('{"rows": {"k": 1, "j": 2}, "nums2": [10, 20, 30]}')
        v = d2[what]
        try:
            print(what, "pop()", v.pop())
        except TypeError as e:
            print(what, "pop() TypeError", e)
        try:
            print(what, "pop('k')", v.pop("k"))
        except TypeError as e:
            print(what, "pop('k') TypeError", e)
        try:
            print(what, "pop(0)", v.pop(0))
        except KeyError as e:
            print(what, "pop(0) KeyError", e)
        print(what, v)
    # a method's result is a union value again
    print(doc["text"].split(", ")[0].upper(), row.get("name", "none").upper(), len(doc["text"].split()))
    # a program's own alias and a union of scalars
    own: Value = {"a": [1, 2], "b": "text"}
    print(own.get("a"), own.get("b").upper(), sorted(own.keys()))
    small: int | str = pick(True)
    print(small.upper())
    try:
        print(pick(False).upper())
    except AttributeError as e:
        print("AttributeError", e)


def pick(text: bool) -> int | str:
    if text:
        return "pq"
    return 7


main()
