# % formatting with a tuple | None on the right: the tuple's items are the arguments, and None
# is one argument, as CPython takes it


def pair(flag: bool) -> tuple[str, int] | None:
    return ("a", 1) if flag else None


def one(flag: bool) -> tuple[str] | None:
    return ("a",) if flag else None


def char(flag: bool) -> str | None:
    return "z" if flag else None


print("%s" % one(True), "%s" % one(False), "[%5s]" % one(False), "%r" % one(False))
print("%s %s" % pair(True), "%s-%d" % pair(True))
t = pair(True)
if t is not None:
    print("%s %s" % t)
print("%c" % char(True))
print("%s %s" % pair(False))
