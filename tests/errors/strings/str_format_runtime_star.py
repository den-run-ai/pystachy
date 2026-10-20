# error: str_format_runtime_star.py:4: error: str.format() of a format string computed at run time is not supported (only of a string literal, "{}".format(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# fmt.format(*xs) of a format string known only when it runs (not the list's * that is unsupported)
def join(fmt: str, xs: list[int]) -> str:
    return fmt.format(*xs)


print(join("{}-{}", [1, 2]))
