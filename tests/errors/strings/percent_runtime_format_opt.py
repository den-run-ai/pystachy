# error: percent_runtime_format_opt.py:3: error: % formatting with a format string computed at run time is not supported (only of a string literal, "%d" % x, or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
def f(fmt: str | None) -> str:
    return fmt % 3


print(f("%d"))
