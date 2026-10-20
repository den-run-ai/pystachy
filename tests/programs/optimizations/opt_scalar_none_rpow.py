# int ** int | None with None: CPython's TypeError, which names pow() too
def gi(flag: bool) -> int | None:
    return 3 if flag else None


print(3 ** gi(True), gi(True) ** 2)
print(3 ** gi(False))
