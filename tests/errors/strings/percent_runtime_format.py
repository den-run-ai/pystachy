# error: percent_runtime_format.py:5: error: % formatting with a format string computed at run time is not supported (only of a string literal, "%d" % x, or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# fmt % x where fmt is known only when it runs: CPython formats x with whatever fmt holds,
# while Pystachy compiles each conversion of a literal format
def f(fmt: str, x: float) -> str:
    return fmt % x


print(f("%.2f", 1.5))
