"""A recursive alias's value is indexed, measured and stored into without narrowing: the member
that its tag names takes the operation, and a member that cannot raises CPython's error."""
import json

type Value = None | bool | int | float | str | list[Value] | dict[str, Value]

CALLS: list[str] = []


def key(name: str) -> str:
    CALLS.append(name)
    return name


def at(i: int) -> int:
    CALLS.append(str(i))
    return i


def read(label: str, text: str) -> None:
    value = json.loads(text)
    try:
        print(label, "len", len(value))
    except TypeError as e:
        print(label, "len TypeError", e)
    try:
        print(label, "[0]", value[0])
    except (TypeError, KeyError, IndexError) as e:
        print(label, "[0]", type(e).__name__, e)
    try:
        print(label, "['a']", value["a"])
    except (TypeError, KeyError, IndexError) as e:
        print(label, "['a']", type(e).__name__, e)
    try:
        print(label, "[-1]", value[-1])
    except (TypeError, KeyError, IndexError) as e:
        print(label, "[-1]", type(e).__name__, e)
    try:
        print(label, "[True]", value[True])
    except (TypeError, KeyError, IndexError) as e:
        print(label, "[True]", type(e).__name__, e)


def write(label: str, text: str) -> None:
    value = json.loads(text)
    try:
        value[0] = "zero"
        print(label, "[0]=", value)
    except (TypeError, IndexError) as e:
        print(label, "[0]=", type(e).__name__, e)
    value = json.loads(text)
    try:
        value["k"] = [1, None]
        print(label, "['k']=", value)
    except (TypeError, IndexError) as e:
        print(label, "['k']=", type(e).__name__, e)
    value = json.loads(text)
    try:
        value[-1] = 2.5
        print(label, "[-1]=", value)
    except (TypeError, IndexError) as e:
        print(label, "[-1]=", type(e).__name__, e)


def own(value: Value) -> None:
    # a program's own alias, a parameter and a local
    print(len(value), value["rows"][1]["id"], value["rows"][0]["tags"][-1][0])
    rows = value["rows"]
    rows[0]["tags"] = []
    rows[1]["id"] = value["rows"][1]["id"]
    value["count"] = len(rows)
    print(value)


CASES: list[str] = ['{"a": [1, {"b": "deep"}], "n": 3}', '[10, "x", null, [1, 2]]', '"h\\u00e9llo"', "7", "2.5",
                    "true", "null", "[]", "{}", '""']
NAMES: list[str] = ["dict", "list", "str", "int", "float", "bool", "None", "empty list", "empty dict", "empty str"]
for i in range(len(CASES)):
    read(NAMES[i], CASES[i])
for i in range(len(CASES)):
    if NAMES[i] not in ["dict", "empty dict"]:
        write(NAMES[i], CASES[i])

doc = json.loads('{"a": [1, {"b": "deep"}], "n": 3, "s": "text"}')
print(doc["a"][1]["b"], doc["n"], len(doc), len(doc["a"]), len(doc["s"]), doc["s"][1])
print(doc["a"][1]["b"][0], doc["a"][-1]["b"][-1])
# the index is evaluated once, after the value, and before a member's error
print(doc[key("a")][at(1)][key("b")], CALLS)
try:
    print(doc[key("n")][at(5)])
except TypeError as e:
    print("TypeError", e, CALLS)
inner = doc["a"]
inner[0] = "changed"
print(doc["a"][0], doc)
doc["a"][1]["b"] = None
doc["a"][1]["c"] = {"new": [True]}
doc["n"] = doc["n"]
doc["m"] = json.loads("[1, 2]")
doc["empty"] = []
doc["empty"] = {}
print(doc, len(doc), len(doc["empty"]))
own({"rows": [{"tags": ["x", "yz"]}, {"id": 7}]})
