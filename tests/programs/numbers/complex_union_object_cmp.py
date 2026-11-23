# An int member and an object whose class defines no __eq__: CPython compares them by identity,
# never equal, as it does the complex member (complex_union_object_eq.py)
class Plain:
    pass


def f(v: int | complex) -> bool:
    return v == Plain()


def g(v: int | complex) -> bool:
    return Plain() != v


print(f(1j), f(1), g(1j), g(1))
