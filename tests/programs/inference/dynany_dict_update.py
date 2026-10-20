# pystachy: dynamic-any
# dict.update() of an Any dict takes a dict display, another dict, a list of pairs and keywords,
# as CPython's does (#782), and CPython's TypeError and ValueError for another argument.
from typing import Any

d: Any = {"a": 1}
d.update({"b": "two", "c": None})
print(d)
other: Any = {"a": 10, "z": [1]}
d.update(other)
pairs: Any = [("p", 1), ["q", 2]]
d.update(pairs)
print(d)
for bad in [5, [("x", 1, 2)], ["ab", "c"]]:
    arg: Any = bad
    try:
        d.update(arg)
        print("updated", d.get("a"))
    except (TypeError, ValueError) as err:
        print(type(err).__name__ + ":", err)
