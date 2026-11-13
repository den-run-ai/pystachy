# == and != between None and a complex | None: CPython compares them by identity, so a value
# that holds None equals None, from either side, and one that holds a complex number does not
def get(flag: bool) -> complex | None:
    return 1j if flag else None


def eq(v: complex | None) -> bool:
    return v == None


x = get(False)
y = get(True)
print(x == None, None == x, x != None, None != x, x is None)
print(y == None, None == y, y != None, None != y, y is None)
print(eq(x), eq(y), eq(get(False)), 2j == None, None != 0j)
