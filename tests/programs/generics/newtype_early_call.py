# N = NewType("N", int) binds N where it runs: a function that calls N(x) and runs before that,
# here from module code above it, raises CPython's NameError; after it, N(x) is x.
from typing import NewType


def make() -> int:
    return N(3) + 1


try:
    print(make())
except NameError as e:
    print("NameError", e)
N = NewType("N", int)
print(make(), N(4))
