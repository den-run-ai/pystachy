from __future__ import annotations

# Deliberately no dynamic-any directive: dumpsvalues opts in and gives this module Any values.
# json.dumps() of one is the dynamic encoder's here too, as it is in a module that opts in: the
# values are Any's containers, which json's own JSONValue function cannot take.
import json

import dumpsvalues


def noisy(tag: str, value: bool) -> bool:
    print("eval", tag)
    return value


doc = dumpsvalues.table(7)
print(json.dumps(doc))
print(json.dumps(doc, sort_keys=True, separators=(",", ":")))
print(json.dumps(obj=doc, ensure_ascii=False))
print(json.dumps(doc["rows"]), json.dumps(doc["t"]), json.dumps(doc["big"]))
print(json.dumps(dumpsvalues.table(3)["rows"][5]))
for kind in ["int", "float", "str", "bool", "none"]:
    print(kind, json.dumps(dumpsvalues.scalar(kind)))
# the arguments are evaluated once, in order
print(json.dumps(dumpsvalues.table(int(noisy("obj", True))), ensure_ascii=noisy("ascii", False), sort_keys=noisy("sort", True)))
# no copy: a later change of the same object is encoded
rows = doc["rows"]
rows.append("later")
print(json.dumps(doc["rows"]))
# the encoder's own errors
try:
    json.dumps(dumpsvalues.ring())
except ValueError as e:
    print("ValueError", e)
try:
    json.dumps(dumpsvalues.point())
except TypeError as e:
    print("TypeError", e)
try:
    json.dumps(dumpsvalues.nan_row(), allow_nan=False)
except ValueError as e:
    print("ValueError", e)
print(json.dumps(dumpsvalues.nan_row()))
# typed values keep JSONValue's function: a display, a decoded document, a typed list
print(json.dumps({"a": [1, 2.5, None, "é"], "b": {}}), json.dumps([1, "x"]), json.dumps(json.loads('{"a": [1, {"b": null}]}')))
typed: list[json.JSONValue] = ["x", "y"]
print(json.dumps(typed), json.dumps("s"), json.dumps(3), json.dumps(None), json.dumps(obj=[True]))
