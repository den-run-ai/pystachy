# pystachy: dynamic-any
# A tuple whose items one side holds as Any values and the other as typed ones converts item by
# item: a typed item is boxed where an Any item is declared (as tomllib's parse_value returns the
# tuple[Pos, str] of its string parsers as a tuple[Pos, Any]), and an Any item is checked and
# unboxed where a typed one is (raising TypeError where its type differs, a deviation:
# tests/deviations/dynany_tuple_item_check.py)
from typing import Any


def lit(s: str) -> tuple[int, str]:
    return len(s), s


def value(s: str) -> tuple[int, Any]:
    if s == "t":
        return 4, True
    if s == "n":
        return 9, None
    if s == "f":
        return 1, 2.5
    if s == "l":
        return 2, [1, "x"]
    if s == "p":
        return 3, (1, "y")
    return lit(s)


for s in ["ab", "t", "n", "f", "l", "p"]:
    pos, v = value(s)
    print(pos, v, value(s), type(v).__name__)

rows: list[tuple[str, Any]] = []
k: Any = "a"
rows.append((k, 1))
rows.append(("b", [1, "x"]))
print(rows)


def pair(flag: bool) -> tuple[str, Any, bool]:
    key: Any = "k" if flag else "j"
    val: Any = 1.5 if flag else {"n": 1}
    return key, val, flag


print(pair(True), pair(False))
