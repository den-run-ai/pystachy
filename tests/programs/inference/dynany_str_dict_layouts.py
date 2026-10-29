# pystachy: dynamic-any
# Immediate string kinds retain Python's slots and stored hashes across all table operations.
from typing import Any


def strings() -> None:
    d: dict[str, int] = {}
    boxed: dict[Any, Any] = {}
    values: dict[str, Any] = {}
    for i in range(40):
        key = "key-" + str(i)
        d[key] = i
        boxed[key] = i
        values[key] = i
    for i in range(0, 40, 2):
        key = "key-" + str(i)
        del d[key]
        del boxed[key]
        del values[key]
    for i in range(0, 40, 4):
        key = "key-" + str(i)
        d[key] = i + 100
        boxed[key] = i + 100
        values[key] = i + 100
    print("equal", d == boxed, boxed == d, values == d, d == values)
    print("order", list(d), list(values))
    copied = d.copy()
    rebuilt = dict(d)
    merged: dict[str, int] = {"prefix": -1}
    merged.update(d)
    print("copies", copied == d, rebuilt == d, merged.pop("prefix"), merged == d)
    merged |= {"tail": 70}
    union = d | {"tail": 70}
    print("union", merged == union, merged.popitem(), merged == d)
    print("fromkeys", dict.fromkeys(d, 9) == dict.fromkeys(list(d), 9))
    print("lookup", d.get("key-39"), d.setdefault("key-1", 100), d.pop("missing", -1))
    copied.clear()
    copied.update(d)
    print("clear", copied == d)


def bytes_keys() -> None:
    d: dict[bytes, int] = {b"one": 1, b"two": 2, b"three": 3}
    del d[b"two"]
    d[b"two"] = 20
    copied = d.copy()
    rebuilt = dict(d)
    copied.update({b"four": 4})
    union = d | {b"four": 4}
    print("bytes", copied == union, rebuilt == d, copied.popitem(), copied == d)
    print(list(d), dict.fromkeys(d, 8), d.get(b"two"), d.pop(b"missing", -1))


strings()
bytes_keys()
