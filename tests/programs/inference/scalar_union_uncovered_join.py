# The branches leave the union: its str has no + with an int, as in CPython.
def unsafe(flag: bool) -> int:
    value: int | str = 1
    if flag:
        value = 2
    else:
        value = "changed"
    return value + 1

print(unsafe(False))
