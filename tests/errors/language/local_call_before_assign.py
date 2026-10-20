# error: local variable 'sqrt' is read before its first assignment
# A call of a name the function assigns later does not call the imported function.
from math import sqrt


def h() -> float:
    y = sqrt(4.0)
    sqrt = 3.0
    return y + sqrt


print(h())
