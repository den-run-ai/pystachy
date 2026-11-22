# An ordering of closed unions selects the comparison of the two members by their tags.
def less(a: int | str, b: int | str) -> bool:
    return a < b

print(less(1, 2))
