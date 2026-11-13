# == and != of a complex number and an int, float or bool | None: None equals only None, also a
# complex | None holding None; a number equals a complex number with a zero imaginary part, as
# complex's comparison finds (tuple search: complex_optional_number_search.py)
def number(flag: bool) -> int | None:
    return 1 if flag else None


def real(flag: bool) -> float | None:
    return 1.0 if flag else None


def truth(flag: bool) -> bool | None:
    return True if flag else None


def cx(flag: bool) -> complex | None:
    return 1 + 0j if flag else None


for fn in [True, False]:
    for fc in [True, False]:
        n = number(fn)
        f = real(fn)
        b = truth(fn)
        c = cx(fc)
        print(fn, fc, n == c, c == n, n != c, f == c, c != f, b == c, c == b)
