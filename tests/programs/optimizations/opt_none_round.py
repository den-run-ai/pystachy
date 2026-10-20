# round() of an int | None that is None raises CPython's TypeError
def gi(flag: bool) -> int | None:
    return 3 if flag else None


print(round(gi(True)), round(gi(True), -1))
print(round(gi(False)))
