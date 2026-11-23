# Builtin containers implement a Protocol's operators: o[k], k in o, len(o), o[k] = v.
from typing import Protocol


class Lookup(Protocol):
    def __getitem__(self, key: int) -> str: ...

    def __contains__(self, key: int) -> bool: ...

    def __len__(self) -> int: ...


class Squares:
    def __getitem__(self, key: int) -> str:
        if key < 0:
            raise KeyError(key)
        return str(key * key)

    def __contains__(self, key: int) -> bool:
        return key >= 0

    def __len__(self) -> int:
        return 99


class Store(Protocol):
    def __setitem__(self, key: str, value: int) -> None: ...

    def __getitem__(self, key: str) -> int: ...


class Indexed(Protocol):
    def __getitem__(self, key: int) -> str: ...

    def __len__(self) -> int: ...


live = {1: "one", 2: "two"}
tables: list[Lookup] = [live, Squares()]
for t in tables:
    print(t[1], 2 in t, 5 in t, len(t))
live[5] = "five"
print(5 in tables[0], len(tables[0]))
try:
    print(tables[0][9])
except KeyError as e:
    print("KeyError", e)
rows: list[Indexed] = [["zero", "one"], live, Squares(), "xyz"]
print([r[1] for r in rows], [len(r) for r in rows])
try:
    print(rows[0][9])
except IndexError as e:
    print("IndexError", e)
d: dict[str, int] = {}
s: Store = d
s["a"] = 3
print(d, s["a"])
