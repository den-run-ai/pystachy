# An optional import in a function whose handler returns: the read of the imported name after
# the try never runs where the import fails, so it is no read of an unbound local.
def slow() -> int:
    return 1


def helper() -> int:
    return 2


def f() -> int:
    try:
        from _accel_missing import helper
    except ImportError:
        return slow()
    return helper()


def g(xs: list[int]) -> int:
    t = 0
    for x in xs:
        try:
            from _accel_missing import helper
        except ImportError:
            t += x
            continue
        t += helper()
    return t


print(f(), g([1, 2, 3]))
