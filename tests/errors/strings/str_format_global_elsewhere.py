# error: str_format_global_elsewhere.py:12: error: str.format() of a format string computed at run time is not supported (only of a string literal, "{}".format(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# a module global bound once to a literal, whose name a function's local also binds: the
# program binds the name twice, so the format is not taken as known (CPython prints "local <1>")
FMT = "<{}>"


def other() -> str:
    FMT = "local"
    return FMT


print(other(), FMT.format(1))
