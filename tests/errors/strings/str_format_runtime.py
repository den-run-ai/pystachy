# error: str_format_runtime.py:5: error: str.format() of a format string computed at run time is not supported (only of a string literal, "{}".format(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# fmt.format(x) where fmt is known only when it runs: CPython reads whatever fmt holds, while
# Pystachy compiles the fields of a literal format
def f(fmt: str, x: int) -> str:
    return fmt.format(x)


print(f("{:>4}", 1))
