# error: may be None
def maybe(flag, a, b):
    if flag:
        return None
    return [a, b]


result: list[int | float] = maybe(False, 1, 2.5)
