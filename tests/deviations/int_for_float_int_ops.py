# Documented deviation: an int argument for a float parameter compiles the function for the int
# (docs/language/typing.md, "int arguments for float parameters"), so its body follows Pystachy's
# int rules where CPython computes with the int as well: a product past 64 bits raises
# OverflowError, where CPython returns the exact int, and int ** negative int raises ValueError,
# where CPython returns a float. Earlier releases rejected these calls at compile time.
# A float argument computes in floats, as in CPython.


def power(base: float, exp: float) -> float:
    return base ** exp


def area(w: float, h: float) -> float:
    return w * h


try:
    print(power(10, -3))
except ValueError as e:
    print("caught:", e)
try:
    print(area(2**40, 2**40))
except OverflowError as e:
    print("caught:", e)
print(power(10.0, -3), area(2.0**40, 2**40))
