# x in range(...) of an int | None or bool | None: None equals no item, once the range is checked
def gi(flag: bool) -> int | None:
    return 2 if flag else None


def gb(flag: bool) -> bool | None:
    return True if flag else None


x: int | None = None
print(x in range(3), x not in range(3), gi(True) in range(3), gi(True) not in range(0, 10, 3), gb(True) in range(2), gb(False) in range(2))
print(gi(False) in range(0, 3, 0))
