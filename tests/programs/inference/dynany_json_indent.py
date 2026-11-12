# pystachy: dynamic-any
# json.dumps() and json.dump() of Any values with an indent: tuples, keys that are not str,
# skipped keys (a dict whose every key is skipped keeps its two line breaks), default= and
# check_circular.
import json
import os
from typing import Any


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def enc(o: Any) -> Any:
    if isinstance(o, Point):
        return {"x": o.x, "y": [o.y, ()]}
    raise TypeError("no")


doc: Any = {"b": [1, 2.5, "x", None, True, [], {}, ()], 3: {"k": ([1], {"z": 0})}, None: "é\n", 1.5: False}
print(json.dumps(doc, indent=2))
print(json.dumps(doc, indent=0))
print(json.dumps(doc, indent=-1))
print(json.dumps(doc, indent="\t", ensure_ascii=False))
print(json.dumps(doc, indent=1, separators=(" ,", " = ")))
print(json.dumps(doc, indent=None) == json.dumps(doc))
mixed: Any = {(1, 2): "skipped", "kept": [Point(1, 2)], ("a",): {("b",): 1}}
print(json.dumps(mixed, indent=2, skipkeys=True, default=enc))
only: Any = {(1,): 1, (2,): {(3,): 3}}
print(repr(json.dumps(only, indent=2, skipkeys=True)), repr(json.dumps([only, {}], indent=1, skipkeys=True)))
print(json.dumps({"z": 1, "a": {"y": [2], "b": 3}}, indent=4, sort_keys=True))
loop: Any = [1]
loop.append(loop)
try:
    json.dumps(loop, indent=2)
except ValueError as e:
    print("ValueError", e)
try:
    json.dumps({"p": Point(0, 0)}, indent=2)
except TypeError as e:
    print("TypeError", e)
loaded: Any = json.loads('[{"a": [1, {"b": null}]}, "x"]')
loaded[0]["a"].append({"c": (1, 2)})
print(json.dumps(loaded, indent=3))
path = "/tmp/pystachy_dynany_json_indent_%d.json" % os.getpid()
with open(path, "w") as fp:
    json.dump(loaded, fp, indent="  ", sort_keys=True)
with open(path) as fp:
    text = fp.read()
os.remove(path)
print(text == json.dumps(loaded, indent=2, sort_keys=True), text.count("\n"))
print(repr(json.dumps(loaded, indent=True)), repr(json.dumps([1, (2,)], indent=False)))
try:
    json.dumps(loaded, indent=1.5)
except TypeError as e:
    print("TypeError", e)
pad: Any = 2
print(json.dumps({"a": [1]}, indent=pad) == json.dumps({"a": [1]}, indent="  "))
