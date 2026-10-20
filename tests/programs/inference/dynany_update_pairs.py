# pystachy: dynamic-any
# dict.update() of an Any dict with an iterable of pairs takes each pair's items as CPython does,
# by iterating it: a list's, a tuple's, a str's characters and a dict's keys, two of them each,
# else CPython's ValueError for another length and TypeError for no iterable or a key no dict takes.
from typing import Any

d: Any = {}
pairs: Any = [{"a": 1, "b": 2}, ("c", 3), "de", ["f", 4]]
d.update(pairs)
print(d)
bads: list[Any] = [[{"x": 1}], [{"x": 1, "y": 2, "z": 3}], [5], [[[1], 2]], ["ok", "xyz"]]
for bad in bads:
    try:
        d.update(bad)
        print(d)
    except (TypeError, ValueError) as err:
        print(type(err).__name__ + ":", err)
print(d)
