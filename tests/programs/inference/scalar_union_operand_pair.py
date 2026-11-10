# Both operands of a binary operator conditional or boolean expressions, where the result is
# wanted as a closed union that has no such operation: each keeps the scalar type its arms
# share, also where the two types differ (an int and a str), and the right one is compiled
# for the union as the left one's type (see scalar_union_conditional_operand.py)
import sys


def repeat(a: int, b: int, c: bool, d: bool) -> int | str:
    return (a if c else b) * ("ab" if d else "c")


def repeated(s: str, a: int, c: bool) -> int | str:
    return (s if c else "-") * ((a if c else 2) or 1)


def joined(s: str, t: str, c: bool) -> int | str:
    return (s if c else t) + ((t or "-") if c else (s and "+"))


def shifted(a: int, b: int, c: bool) -> int | float:
    return (a if c else b) << ((1 if c else 2) or 3)


def powered(a: int, b: int, x: float, c: bool) -> int | float:
    # (a literal exponent that is not negative: the power has its operand's type)
    return (a if c else b) ** 3 + ((x if c else 0.5) or 2.0) ** 2


def ored(a: int, b: int, c: bool) -> int | str:
    return ((a if c else b) or (b if c else a)) | ((a and b) if c else (a or b))


def halved(a: int, b: int, c: bool) -> float | str:
    return ((a if c else b) or 1) / ((2 if c else 4) and (b or 8))


def masked(a: int, b: int, c: bool) -> int | str:
    return ((a if c else b) * 31 + ((b if c else a) or 7)) & ((0xFF if c else 0xF) or 1)


def show(v: int | float | str) -> str:
    return repr(v) + ":" + type(v).__name__


z = len(sys.argv) // 100  # (0, not a constant)
print(show(repeat(1 + z, 2, True, True)), show(repeat(1, 2 + z, False, False)), show(repeat(z, 2, True, False)), show(repeated("ab", z, True)), show(repeated("ab", 3 + z, True)), show(repeated("ab", 3, False)))
print(show(joined("s" * (z + 1), "t", True)), show(joined("s", "", True)), show(joined("", "t", False)), show(joined("s", "t" * (z + 1), False)))
print(show(shifted(3 + z, 5, True)), show(shifted(3, 5 + z, False)), show(powered(3 + z, 5, 1.5, True)), show(powered(3, 5 + z, 1.5, False)), show(ored(z, 6, True)), show(ored(z, 0, True)), show(ored(5 + z, 2, False)))
print(show(halved(6 + z, 0, True)), show(halved(z, 0, False)), show(halved(z, 3, False)), show(masked(1000 + z, 3, True)), show(masked(z, 3, True)), show(masked(1000, z, False)))
