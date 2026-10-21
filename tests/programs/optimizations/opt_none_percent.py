# "%d" with an argument that is None (a tuple | None that is None) raises CPython's error


def one(flag: bool) -> tuple[int] | None:
    return (7,) if flag else None


print("%x" % one(True))
print("%x" % one(False))
