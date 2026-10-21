# pystachy: dynamic-any
# items() of a dict[str, Any] where typed code expects a list[tuple[str, Any]], and list() and
# sorted() of them: tuples of the keys unboxed and the values, in a new list (#777)
from typing import Any


def items(d: dict[str, Any]) -> list[tuple[str, Any]]:
    return d.items()


def ordered(d: dict[str, Any]) -> list[tuple[str, Any]]:
    return sorted(d.items())


def copied(d: dict[str, Any]) -> list[tuple[str, Any]]:
    return list(d.items())


doc: dict[str, Any] = {"b": 1, "a": [2, "x"], "c": None}
for k, v in items(doc):
    print(k.upper(), v)
print(list(items(doc)), len(items(doc)))
print([k + "!" for k, v in ordered(doc)], copied(doc))
