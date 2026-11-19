# error: cannot compare int == Plain
# An int member and an object whose class defines no __eq__ (CPython compares them by identity).
class Plain:
    pass


def f(v: int | complex) -> bool:
    return v == Plain()


print(f(1j))
