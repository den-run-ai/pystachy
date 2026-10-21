# A specialized builtin call still reads its alias, even when its result is constant.
from struct import calcsize


def use() -> int:
    return size("i")


try:
    print(use())
except NameError as e:
    print("NameError", e)
size = calcsize
print(use())
