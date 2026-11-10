# A boolean operation as the left operand of a binary operator, where the operation's result
# is wanted as a closed union that has no such operation: its operands, and the arms of a
# conditional expression among them, keep the scalar type they share (see
# scalar_union_conditional_operand.py; int | float has a division, which runs on the union)
def bool_or(a: int, b: int, c: bool) -> int | str:
    return ((a if c else b) or 7) * 2 + (a or b) - ((a and b) or 1)


def bool_and(a: int, b: int, c: bool) -> int | float:
    return ((a if c else b) and (b & 3)) / 4


def bool_str(s: str, c: bool) -> int | str | None:
    return (("" if c else s) or s[:2]) + ("x" if c else s)


def bool_float(x: float, c: bool) -> str | float:
    return ((1.5 if c else x) or -0.25) * x


def bool_opt(o: int | None, n: int) -> int | str:
    return ((o if o is not None else n) or 1) // 2 + ((o or n) and 3)


def bool_nested(a: int, b: int, c: bool) -> int | str:
    return (((a if c else b) or (b if c else a)) and ((a or b) if c else (a and b))) % 7


def bool_static(a: int, b: int) -> int | str:
    return ((a if True else b) or (b if False else a)) + 1


print(bool_or(3, 4, True), bool_or(0, 4, True), bool_or(0, 0, False), bool_and(3, 6, True), bool_and(0, 6, True), bool_and(5, 7, False))
print(bool_str("abc", True), bool_str("abc", False), bool_str("", False), bool_float(2.0, True), bool_float(0.0, False))
print(bool_opt(None, 0), bool_opt(None, 9), bool_opt(8, 1), bool_opt(0, 5), bool_nested(3, 4, True), bool_nested(0, 4, False), bool_nested(0, 0, True), bool_static(0, 5))
