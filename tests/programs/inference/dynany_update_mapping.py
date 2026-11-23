# pystachy: dynamic-any
# d.update(m), d |= m and dict(m) of an Any value m whose class has keys() merge it as CPython's
# dict_update_arg does: keys() first, as a list, then m[k] for each key in turn, not m's iteration
# as pairs; a dict's items, and pairs, merge as before.
from typing import Any


class Mapping:
    def __init__(self, data: dict[str, int]) -> None:
        self.data = data

    def keys(self) -> list[str]:
        print("keys")
        return list(self.data.keys())

    def __getitem__(self, key: str) -> int:
        print("getitem", key)
        return self.data[key]

    def __iter__(self) -> Any:
        print("iter")
        return iter(["xy"])


class Lazy:
    def keys(self) -> Any:
        print("Lazy.keys")
        for k in ["ab", "cd"]:
            print("yield", k)
            yield k

    def __getitem__(self, key: str) -> str:
        print("Lazy.getitem", key)
        return key.upper()


class KeysOnly:
    def __init__(self, keys: list[str]) -> None:
        self.names = keys

    def keys(self) -> list[str]:
        return self.names


class Pairs:
    def __iter__(self) -> Any:
        return iter([("p", 1), ("q", 2)])


def merge(d: Any, m: Any) -> None:
    d.update(m)
    print(d)


def merged(m: Any) -> None:
    try:
        print(dict(m))
    except (TypeError, ValueError) as error:
        print(type(error).__name__, error)


merge({}, Mapping({"ab": 1, "cd": 2}))
merge({"ab": 0}, Lazy())
merge({}, {"k": 1})
merge({}, [("ab", 3)])
merge({}, Pairs())
both: Any = {"z": 0}
both |= Mapping({"ab": 1})
print(both)
merged(Mapping({"ab": 4}))
merged(Lazy())
merged({"a": 1})
merged([("a", 1), ["b", 2]])
merged(Pairs())
merged(KeysOnly([]))
merged(KeysOnly(["a"]))
merged(5)
merged(None)
merged(["abc"])
original: Any = {"a": [1]}
copied = dict(original)
print(copied == original, copied is original, copied["a"] is original["a"])
