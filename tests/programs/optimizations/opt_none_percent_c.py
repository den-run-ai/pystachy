# %c with a str | None that is None raises CPython's error


def char(flag: bool) -> str | None:
    return "z" if flag else None


print("%c" % char(True))
print("%c" % char(False))
