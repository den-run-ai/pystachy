# json.dumps() and json.dump() with an indent: an int, a str, zero, a negative int, with and
# without separators, empty containers on one line, and nesting.
import json
import os

doc = json.loads('{"b": [1, 2.5, "x", null, true, [], {}], "a": {"k": [[1], {"z": 0}]}, "e": "é\\n"}')
print(json.dumps(doc, indent=2))
print(json.dumps(doc, indent=0))
print(json.dumps(doc, indent=-3))
print(json.dumps(doc, indent="\t"))
print(json.dumps(doc, indent="--", sort_keys=True, ensure_ascii=False))
print(json.dumps(doc, indent=1, separators=(" ,", " = ")))
print(json.dumps(doc, indent=None), json.dumps(doc))
print(json.dumps([], indent=4), json.dumps({}, indent=4), json.dumps([[]], indent=4), json.dumps(7, indent=4), json.dumps("s", indent=4))
print(repr(json.dumps([1, [2, [3]]], indent="")))
width = int(os.environ.get("JSON_INDENT_WIDTH", "3"))
print(json.dumps({"n": [1, {"m": None}]}, indent=width))
path = "/tmp/pystachy_json_indent_%d.json" % os.getpid()
with open(path, "w") as fp:
    json.dump(doc, fp, indent=2, sort_keys=True)
with open(path) as fp:
    text = fp.read()
os.remove(path)
print(text == json.dumps(doc, indent=2, sort_keys=True), json.loads(text) == doc, text.count("\n"))
print(repr(json.dumps([1, [2]], indent=True)), repr(json.dumps([1, [2]], indent=False)))
try:
    json.dumps([1], indent=1.5)
except TypeError as e:
    print("TypeError", e)
