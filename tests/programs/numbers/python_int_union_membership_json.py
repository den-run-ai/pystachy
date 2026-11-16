# pystachy: python-int
# A tuple's in, not in, count() and index() compare a promoting int with a recursive alias's union
# (json.JSONValue), which may also hold None, lists and dicts, as CPython compares them (#1354):
# an int, bool or float of the same value, where the promoting int fits 64 bits, and only a float
# of its value past 64 bits.
import json


def search(value: "json.JSONValue", t: tuple[int, str]) -> None:
    print(repr(value), t[0], value in t, value not in t, t.count(value), t[0] in (value,), (value, t[0]).index(t[0]))


VALUES: "list[json.JSONValue]" = [1, 1.0, True, "a", None, [1], {"a": 1}, 2**62, 2.0**62, 2.0**70, 0, False]
for t in [(1, "a"), (0, "a"), (2**62, "a"), (2**70, "a")]:
    for v in VALUES:
        search(v, t)
