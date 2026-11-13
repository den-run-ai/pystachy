# in, count() and index() of tuples of complex numbers and int, float or bool | None values: None
# equals only None, also a complex | None holding None; a number equals a complex number with a
# zero imaginary part (==: complex_optional_number_eq.py)
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
        print(fn, fc, n in (c,), c in (n,), (c, 2j).count(n), (n, c).index(c), f in (c,), c in (b,))
