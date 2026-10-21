# error: double() has no return annotation, which the type variable it matches takes its type from
from functools import cache


@cache
def double(x: int):
    return x * 2


print(double(1))
