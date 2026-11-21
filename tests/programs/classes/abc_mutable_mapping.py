# A class deriving from collections.abc.MutableMapping defines the five abstract methods and
# inherits the others from lib's port of CPython's _collections_abc: get, in, keys, items, values,
# ==, pop, popitem, clear, update (a mapping, pairs, keywords) and setdefault
from collections.abc import MutableMapping


class Lower(MutableMapping):
    def __init__(self) -> None:
        self.d: dict[str, int] = {}

    def __getitem__(self, k: str) -> int:
        return self.d[k.lower()]

    def __setitem__(self, k: str, v: int) -> None:
        self.d[k.lower()] = v

    def __delitem__(self, k: str) -> None:
        del self.d[k.lower()]

    def __iter__(self):
        return iter(self.d)

    def __len__(self) -> int:
        return len(self.d)


m = Lower()
m["A"] = 1
m.update({"B": 2})
m.update([("C", 3)])
m.update(D=4)
print(m.get("a"), m.get("z"), m.get("z", -1), "b" in m, "q" in m, len(m))
print(list(m), list(m.keys()), list(m.items()), list(m.values()))
print(m == {"a": 1, "b": 2, "c": 3, "d": 4}, m == {"a": 1}, m != {"a": 1})
other = Lower()
other.update(m)
print(other == m, len(other))
print(m.pop("a"), m.pop("zz", 0), m.setdefault("e", 5), m.setdefault("e", 6))
try:
    m.pop("nope")
except KeyError as e:
    print("KeyError", e)
print(m.popitem(), len(m))
m.clear()
print(len(m), list(m.items()))
try:
    m.popitem()
except KeyError as e:
    print("KeyError", repr(e))
try:
    hash(m)
except TypeError as e:
    print("TypeError", e)
