# error: str_format_global_local.py:7: error: str.format() of a format string computed at run time is not supported (only of a string literal, "{}".format(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# a function's local with the name of a module global bound to a literal: not that global
FMT = "{}!"


def f(FMT: str) -> str:
    return FMT.format(1)


print(f("{}?"))
