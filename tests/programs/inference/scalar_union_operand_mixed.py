# A conditional or boolean operand of a binary operator whose result is wanted as int | float,
# with ints and floats among the operands: union arithmetic compiles these operations, so the
# operands are the unions they are anywhere else, and the result has its value's type (an
# operand keeps a scalar only for an operation the union has not:
# scalar_union_conditional_operand.py)
import sys


def one_type(a: int, b: int, flag: bool) -> int | float:
    return (a if flag else b) * 2


def or_float(a: int, b: int, flag: bool) -> int | float:
    return ((a if flag else b) or 1.5) * 2


def and_float(a: int, b: int, flag: bool) -> int | float:
    return ((a if flag else b) and 1.5) * 2


def or_int(x: float, y: float, flag: bool) -> int | float:
    return ((x if flag else y) or 1) * 2


def and_int(x: float, y: float, flag: bool) -> int | float:
    return ((x if flag else y) and 1) * 2


def right_arms(a: int, b: int, c: int, flag: bool, other: bool) -> int | float:
    return (a if flag else b) * (1.5 if other else c)


def right_first(a: int, b: int, x: float, flag: bool) -> int | float:
    return (a if flag else b) - (x if flag else b)


def result_or(a: int, b: int, flag: bool) -> int | float:
    return ((a if flag else b) * 2) or 1.5


def result_times(a: int, b: int, c: int, flag: bool, other: bool) -> int | float:
    return ((a if flag else b) * 2) * (1.5 if other else c)


def both_sides(a: int, b: int, flag: bool) -> int | float:
    return ((a if flag else b) or 1.5) + ((b if flag else a) and 2.5)


def sum_arms(a: int, b: int, flag: bool) -> int | float:
    return (a if flag else b) * 2 + (1.5 if flag else b)


def nested(a: int, b: int, x: float, flag: bool) -> int | float:
    return (((a if flag else b) or (b if flag else a)) or (x if a > b else 0.5)) - 1


def chained(a: int, b: int, x: float, flag: bool) -> int | float:
    return ((a if flag else b) and (b if flag else a) and x) * 2 - (a or b)


def optional(a: int, b: int, flag: bool) -> int | float | None:
    return ((a if flag else b) or 2.5) % 2


def stored(a: int, b: int, flag: bool) -> list[int | float]:
    v: int | float = ((a if flag else b) and 0.5) + 1
    return [v, ((a if flag else b) or 0.25) // 1, (b if flag else a) * (0.5 if flag else 2)]


def show(v: int | float | None) -> str:
    return repr(v) + ":" + type(v).__name__


z = len(sys.argv) // 100  # (0, not a constant)
print(show(or_float(z, 0, True)), show(or_float(3, z, True)), show(or_float(0, 4 + z, False)), show(and_float(z, 0, True)), show(and_float(3 + z, 0, True)))
print(show(or_int(0.0, 0.0 + z, True)), show(or_int(3.0, 0.0, True)), show(and_int(0.0, z + 4.0, True)), show(and_int(3.0, 0.0, True)))
print(show(right_arms(1, 2, 3 + z, True, True)), show(right_arms(1, 2 + z, 3, False, False)), show(right_first(5, z, 0.5, True)), show(right_first(5, 2 + z, 0.5, False)))
print(show(result_or(z, 1, True)), show(result_or(0, 1 + z, False)), show(result_times(1, 2, 3, True, True)), show(result_times(1 + z, 2, 3, False, False)))
print(show(both_sides(z, 2, True)), show(both_sides(1, 2 + z, False)), show(both_sides(0, z, True)), show(sum_arms(z, 2, True)), show(sum_arms(1, 2, False)))
print(show(nested(z, 0, 2.5, True)), show(nested(0, 4 + z, 2.5, True)), show(nested(z, -1, 2.5, False)), show(chained(1, 2, 0.0 + z, True)), show(chained(0, 2, 3.5, False)), show(chained(1 + z, 2, 3.5, True)))
print(show(one_type(3 + z, 4, True)), show(one_type(3, 4 + z, False)), show(optional(z, 0, True)), show(optional(7, z, True)), [show(v) for v in stored(z, 3, True)], [show(v) for v in stored(2 + z, 0, False)])
