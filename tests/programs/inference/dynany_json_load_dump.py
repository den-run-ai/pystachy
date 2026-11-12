# pystachy: dynamic-any
# json.load(fp) and json.dump(obj, fp) with Any values.
import json
import os
import tempfile
from typing import Any


def main() -> None:
    d = tempfile.mkdtemp()
    p = os.path.join(d, "a.json")
    doc: Any = {"a": [1, 2.5, None, True, "x"], "big": 1234567890123, "n": {"k": "v"}}
    with open(p, "w") as f:
        json.dump(doc, f, sort_keys=True)
    with open(p) as f:
        print(f.read())
    with open(p) as f:
        back: Any = json.load(f)
    print(back == doc, back["big"] + 1, type(back["a"]).__name__)
    with open(p, "w") as f:
        json.dump([1, "two", {"three": 3.0}], f, ensure_ascii=False, separators=(",", ":"))
    with open(p) as f:
        print(json.load(f))
    with open(p, "w") as f:
        f.write("{bad")
    try:
        with open(p) as f:
            json.load(f)
    except json.JSONDecodeError as e:
        print("error:", e)


main()
