# complex numbers as members of closed scalar unions, as mypy's constant folding holds them
# (ConstantValue = int | bool | float | complex | str): isinstance() narrowing, arithmetic that
# splits by member, equality across members (1 == 1+0j), str/repr/format and abs()
from typing import Optional

ConstantValue = int | bool | float | complex | str


def describe(v: ConstantValue) -> str:
    if isinstance(v, bool):
        return "bool " + str(v)
    if isinstance(v, int):
        return "int " + str(v + 1)
    if isinstance(v, float):
        return "float " + str(v * 2)
    if isinstance(v, complex):
        return "complex " + str(v.conjugate())
    return "str " + v.upper()


def fold(op: str, left: ConstantValue, right: ConstantValue) -> ConstantValue | None:
    if isinstance(left, int) and isinstance(right, int):
        return left + right if op == "+" else left - right
    if op == "+" and isinstance(left, (int, float)) and isinstance(right, complex):
        return left + right
    elif op == "+" and isinstance(left, complex) and isinstance(right, (int, float)):
        return left + right
    elif op == "-" and isinstance(left, (int, float)) and isinstance(right, complex):
        return left - right
    elif op == "-" and isinstance(left, complex) and isinstance(right, (int, float)):
        return left - right
    return None


def numeric(v: int | float | complex, w: int | complex | str) -> None:
    print(v == 1, v != 2j, 1 == v, v == "s", v == w, w != v, v == 2.5)
    print(-v, v * 2, v ** 2, v / 2, v + 1j, abs(v), type(v).__name__)
    print(format(v, ".1f"), f"{v:>8}|{v}|{v!r}", str(v), bool(v))


vals: list[ConstantValue] = [1, True, 2.5, 3 - 4j, "s", 0j]
for v in vals:
    print(describe(v), v, repr(v), bool(v))
print(vals)
print(fold("+", 1, 2j), fold("-", 1j, 2.5), fold("+", 2, 3), fold("*", 1, 2), fold("-", 1.5, 1 + 1j))
numeric(1, 1)
numeric(2.5, 3j)
numeric(3 - 4j, 1)
numeric(1 + 0j, 1.0 + 0j)
numeric(complex(2.5, 0.0), "s")
final_value: int | float | bool | complex | str | None = None
print(final_value, final_value == None, final_value != 1j)
final_value = complex(1.0, 2.0)
if final_value is not None:
    print(final_value, f"{final_value}", final_value == 1 + 2j)
maybe: Optional[int | complex] = None
xs: list[int | complex | None] = [None, 2, 2 + 0j, 1j]
for x in xs:
    maybe = x
    print(maybe, maybe == 2, f"{maybe}")
table: dict[str, int | complex] = {"a": 1, "b": 2j}
print(table, [t == 1 for t in table.values()], [str(t) for t in table.values()])
