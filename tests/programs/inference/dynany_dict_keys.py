# pystachy: dynamic-any
# Keys of Any-keyed dicts (#780). A str key is found by an equal str in another box, such as a
# literal's or one computed at run time, and an int key by an equal int computed apart; ints whose
# hashes collide stay two keys. Equal numbers of other types (1, 1.0, True) are one key, a NaN is
# found only as itself, and an object whose __eq__ takes a str finds that str's entry, also where
# its __eq__ changes the dict
from typing import Any


def joined(parts: list[Any]) -> Any:
    s: Any = ""
    for p in parts:
        s = s + p
    return s


def show(label: str, d: dict[Any, Any]) -> None:
    print(label, d, len(d))


d: dict[Any, Any] = {"type": "literal", "id": 7}
k: Any = joined(["ty", "pe"])
print(k in d, d[k], d.get(k), d.get(joined(["ty", "PE"]), "missing"))
d[k] = "computed"
show("overwritten:", d)
print(d.setdefault(joined(["i", "d"]), 0), d.pop(joined(["i", "d"])), joined(["i", "d"]) in d)
d[joined(["n", "ew"])] = 1
del d[joined(["t", "y", "p", "e"])]
d["type"] = "again"
show("deleted and stored again:", d)
try:
    print(d[joined(["ty", "PE"])])
except KeyError as e:
    print("KeyError", e)

big: dict[Any, Any] = {}
for i in range(200):
    big[joined(["key", str(i)])] = i
total = 0
for i in range(0, 200, 3):
    total += big["key" + str(i)]
print(len(big), total, "key199" in big, "key200" in big)

n: dict[Any, Any] = {}
a: Any = 1000
n[a] = "a"
print(n[int("1000")], int("999") + 1 in n, -1000 in n)
n[-1] = "minus one"
n[-2] = "minus two"
n[2**61 - 1] = "2**61 - 1"
n[0] = "zero"
n[2**61] = "2**61"
n[1] = "one"
print(n[int("-1")], n[int("-2")], n[2**61 - 1], n[0], n[2**61], n[1], len(n))

m: dict[Any, Any] = {}
one: Any = 1
m[one] = "int"
m[1.0] = "float"
m[True] = "bool"
m[2**40] = "big"
show("equal numbers:", m)
print(m[float(2**40)], 1.0 in m, False in m)

nan: Any = float("nan")
f: dict[Any, Any] = {nan: "nan"}
print(nan in f, float("nan") in f, f.get(nan))


class Loose:
    def __init__(self, s: str) -> None:
        self.s = s

    def __eq__(self, other: Any) -> bool:
        return other == self.s

    def __hash__(self) -> int:
        return hash(self.s)


class Pruner:
    def __init__(self, s: str, d: dict[Any, Any]) -> None:
        self.s = s
        self.d = d

    def __eq__(self, other: Any) -> bool:
        if self.s in self.d:
            del self.d[self.s]
        return False

    def __hash__(self) -> int:
        return hash(self.s)


o: dict[Any, Any] = {"type": 1, "id": 2}
print(Loose("type") in o, o[Loose("id")], Loose("other") in o)
print(Pruner("type", o) in o, o)
