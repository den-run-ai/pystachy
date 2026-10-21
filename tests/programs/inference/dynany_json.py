# pystachy: dynamic-any
# json.loads() into Any values and json.dumps() of Any values (#779): its cases, nested documents
# whose containers Any views share and change, tuples, keys that are not str, sort_keys,
# separators, ensure_ascii, and the errors CPython raises for what JSON cannot hold.
import json
from typing import Any


def payload(n: int) -> Any:
    return {"n": n, "ok": n > 1, "tags": ["a"]}


class Point:
    def __init__(self, x: int) -> None:
        self.x = x


def cases() -> None:
    doc: Any = json.loads('{"a": [1, "two", {"b": null}], "n": 2.5}')
    print(1, doc["a"][1], doc["n"] * 2)
    print(2, json.dumps(payload(2)))
    data = {"name": "x", "n": 3, "items": [1, "two", None]}
    print(3, json.dumps(data, sort_keys=True))
    rec: dict[str, Any] = {"name": "x", "n": 3}
    print(4, json.dumps(rec))
    print(5, json.dumps({"name": "x", "n": 3, "items": [1, "two", None, True]}, sort_keys=True))


def shared() -> None:
    doc: Any = json.loads('{"users": [{"name": "ann", "roles": []}, {"name": "bob", "roles": ["admin"]}]}')
    users: list[dict[str, Any]] = doc["users"]
    first: dict[str, Any] = users[0]
    first["roles"].append("dev")
    doc["users"][1]["name"] = "BOB"
    users.append({"name": "cy", "roles": first["roles"]})
    print("shared", users is doc["users"], first is doc["users"][0], doc["users"][2]["roles"] is first["roles"])
    print(json.dumps(doc))
    top: Any = json.loads("[[], {}, [[1.5, -0.0, 1e100]], true, false, null, \"\\u00e9\\ud83d\\ude00\"]")
    print(top, json.dumps(top))
    print(json.dumps(top, ensure_ascii=False))
    big: Any = json.loads("[9223372036854775807, -9223372036854775808, 0.1, 12e-3]")
    print(big, [type(v).__name__ for v in big])


def keys_and_tuples() -> None:
    t: Any = (1, "a", (2.5, None))
    print(json.dumps(t), json.dumps([t, ()]))
    odd: dict[Any, Any] = {1: "int", 2.5: "float", True: "bool", None: "none", "s": "str"}
    print(json.dumps(odd))
    print(json.dumps({3: "c", 1: "a", 2: "b"}, sort_keys=True))
    print(json.dumps({"b": 1, "a": [1, 2], "c": {"y": 2, "x": 1}}, sort_keys=True, separators=(",", ":")))
    print(json.dumps([1, {"k": "v"}], separators=(";", "=")))
    print(json.dumps({"é": "ü", "tab": "\t", "quote": '"'}))
    print(json.dumps({"é": "ü"}, ensure_ascii=False))
    print(json.dumps({(1, 2): "t"}, skipkeys=True), json.dumps([float("nan"), float("inf"), -float("inf")]))


def errors() -> None:
    bad: list[Any] = [{(1, 2): "t"}, {1: "a", "b": 2}, Point(1), lambda z: z, float("nan")]
    for i, v in enumerate(bad):
        try:
            print(json.dumps(v, sort_keys=i == 1, allow_nan=i != 4))
        except (TypeError, ValueError) as e:
            print(i, type(e).__name__, e)
    loop: Any = []
    loop.append(loop)
    try:
        json.dumps(loop)
    except ValueError as e:
        print("loop", e)
    for text in ['{"a": 1,}', "[1, 2", '{"a" 1}', "", "[1] x"]:
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            print(repr(text), e.msg, e.pos, e.lineno, e.colno)


cases()
shared()
keys_and_tuples()
errors()


# a default() callback that changes a later entry of the dict being written: the entry's value
# is read when its key is reached, as CPython's encoder reads it; with sort_keys, the items are
# a list sorted before the callback runs, as CPython's are (#823)
class LiveDefault:
    pass


live_doc: dict[str, Any] = {"a": LiveDefault(), "b": 0}


def live_default(o: Any) -> Any:
    live_doc["b"] = 2
    return 1


print(json.dumps(live_doc, default=live_default))
live_doc["b"] = 0
print(json.dumps(live_doc, default=live_default, sort_keys=True))


# json.dumps(obj=...): the keyword's value chooses the encoder, as a positional one does (#823)
def json_payload() -> Any:
    return {"k": [1, None]}


print(json.dumps(obj=json_payload()))
print(json.dumps(sort_keys=True, obj={2: "y", 1: "x"}))
