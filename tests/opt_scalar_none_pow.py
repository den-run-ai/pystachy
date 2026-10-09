# float | None ** int with None: CPython's TypeError, which names pow() too
def gf(flag: bool) -> float | None:
    return 1.5 if flag else None


x = gf(True)
x **= 2
print(x, gf(True) ** 2, 2 ** gf(True))
print(gf(False) ** 2)
