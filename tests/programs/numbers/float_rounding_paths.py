# math.floor, math.ceil, math.trunc, round(), float.is_integer(), % and // of floats read at run
# time (float_rounding_paths.in), so that nothing folds: whole and fractional values on both sides
# of 2**52 and 2**53 and at the ends of the 64-bit range, ties, signed zeros, infinities and NaN,
# and every sign of the operands
import math
import sys


def one(x: float) -> str:
    parts: list[str] = []
    for name in ["floor", "ceil", "trunc", "round"]:
        try:
            if name == "floor":
                parts.append(str(math.floor(x)))
            elif name == "ceil":
                parts.append(str(math.ceil(x)))
            elif name == "trunc":
                parts.append(str(math.trunc(x)))
            else:
                parts.append(str(round(x)))
        except (ValueError, OverflowError) as e:
            parts.append(type(e).__name__)
    parts.append(str(x.is_integer()))
    return " ".join(parts)


def two(a: float, b: float) -> str:
    try:
        return f"{a % b!r} {a // b!r} {divmod(a, b)!r}"
    except ZeroDivisionError as e:
        return f"ZeroDivisionError {e}"


lines = sys.stdin.read().split("\n")
singles = int(lines[0])
for k in range(1, singles + 1):
    x = float(lines[k])
    print(lines[k], one(x))
for line in lines[singles + 1 :]:
    if line != "":
        a, b = line.split()
        print(a, b, two(float(a), float(b)))
