# A tuple | None that holds two items for one conversion: not all arguments are converted


def pair(flag: bool) -> tuple[str, int] | None:
    return ("a", 1) if flag else None


print("%s" % pair(False))
print("%s" % pair(True))
