# pystachy: dynamic-any
# dictfuse reused the entry that `key in d` found for a later d[key] even where a lookup in between
# ran user code: a dynamic key's __hash__ and __eq__. That code can empty d, so the entry
# was stale (a segmentation fault where CPython raises KeyError), and fusing skipped the second
# lookup's __hash__ call that CPython makes.
from typing import Any

armed: list[bool] = [False]
hashes: list[int] = [0]


class Key:
    """Equal only to itself; once armed, comparing it empties another dict."""

    def __init__(self, name: str, victim: Any) -> None:
        self.name = name
        self.victim = victim

    def __hash__(self) -> int:
        hashes[0] += 1
        return 7

    def __eq__(self, other: object) -> bool:
        if armed[0]:
            self.victim.clear()
        return self is other


def lookup_both(first: Any, second: Any, key: Any) -> Any:
    # json_repair's ObjectComparer.is_same_object: both dicts, then first[key] and second[key]
    if isinstance(first, dict) and isinstance(second, dict):
        if key not in second:
            return None
        armed[0] = True
        # first[key] compares key with first's other key of the same hash: Key.__eq__ empties
        # second before second[key] looks it up
        return [first[key], second[key]]
    return None


def fetch(table: Any, key: Any) -> Any:
    if isinstance(table, dict):
        if key in table:
            return table[key]
    return None


second: Any = {}
key = Key("k", second)
other = Key("o", second)
second[key] = "second's value"
first: Any = {other: "first's other", key: "first's value"}
try:
    print(lookup_both(first, second, key))
except KeyError:
    print("KeyError")
print(len(second))

armed[0] = False
counted = Key("c", {})
table: Any = {counted: "v"}
hashes[0] = 0
print(fetch(table, counted), hashes[0])
plain: Any = {"a": 1, 2: "b"}
print(fetch(plain, "a"), fetch(plain, 2), fetch(plain, "z"))
