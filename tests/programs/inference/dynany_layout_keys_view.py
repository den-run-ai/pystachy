# pystachy: dynamic-any
# keys() of a dict[str, Any] or dict[int, Any] where typed code expects a list of str or int:
# the keys, unboxed into the new list keys() makes, as list(d) does (#777)
from typing import Any


def keys(d: dict[str, Any]) -> list[str]:
    return d.keys()


def shout(xs: list[str]) -> str:
    return " ".join([x.upper() for x in xs])


def ids(d: dict[int, Any]) -> list[int]:
    return d.keys()


doc: dict[str, Any] = {"b": 1, "a": [2, "x"], "c": None}
ks = keys(doc)
print(list(ks), len(ks), "a" in ks, sorted(ks))
print(shout(keys(doc)))
print(sum(ids({3: "x", 1: 2.5})))


def keys_unbound(d: dict[str, Any]) -> list[str]:
    return dict.keys(d)


def keys_saved(d: dict[str, Any]) -> list[str]:
    f = d.keys
    return f()


print(sorted(keys_unbound(doc)), sorted(keys_saved(doc)))
