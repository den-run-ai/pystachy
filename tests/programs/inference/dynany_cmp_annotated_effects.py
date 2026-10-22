# pystachy: dynamic-any
# Concrete annotations do not gate comparison calls. Cover both operand orders,
# inherited methods, tuple/container annotations, container lookups and first errors.
from typing import Any


class Loose:
    def __eq__(self, other: "Loose") -> bool:
        print("eq", type(other).__name__)
        return True

    def __ne__(self, other: "Loose") -> bool:
        print("ne", type(other).__name__)
        return False

    def __lt__(self, other: "Loose") -> bool:
        print("lt", type(other).__name__)
        return True

    def __le__(self, other: "Loose") -> bool:
        print("le", type(other).__name__)
        return True

    def __gt__(self, other: "Loose") -> bool:
        print("gt", type(other).__name__)
        return False

    def __ge__(self, other: "Loose") -> bool:
        print("ge", type(other).__name__)
        return False

    def __hash__(self) -> int:
        return 1


class Child(Loose):
    pass


class Override(Loose):
    def __eq__(self, other: "Override") -> bool:
        print("override eq")
        return False

    def __gt__(self, other: "Override") -> bool:
        print("override gt")
        return True


class TupleComparison:
    def __eq__(self, other: tuple[int, int]) -> bool:
        print("tuple", len(other))
        return other[0] == 7


class ListComparison:
    def __eq__(self, other: list[int]) -> bool:
        print("list", len(other))
        return other == [7]


class Error:
    def __eq__(self, other: "Error") -> bool:
        print("before error")
        raise ValueError("comparison failed")


class Reflected:
    def __eq__(self, other: "Reflected") -> bool:
        print("reflected must not run")
        return True


x: Any = Loose()
one: Any = 1
print(x == one, one == x, x != one, one != x)
print(x < one, one > x, x <= one, one >= x)
print(x > one, one < x, x >= one, one <= x)
child: Any = Child()
print(child == one, one < child)
override: Any = Override()
print(override == one, one == override, one < override)
print(one in [x], [x].count(one), [x].index(one))
table: dict[Any, Any] = {x: "found"}
print(table[one], one in table)
t: Any = TupleComparison()
pair: Any = (7, 2)
longer: Any = (7, 2, 3)
print(t == pair, t == longer, longer == t)
lst: Any = ListComparison()
values: Any = [7]
print(lst == values, values == lst)
error: Any = Error()
reflected: Any = Reflected()
try:
    print(error == reflected)
except ValueError as exc:
    print(type(exc).__name__, str(exc))
