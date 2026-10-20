# error: str_format_runtime_dstar.py:5: error: str.format() of a format string computed at run time is not supported (only of a string literal, "{}".format(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# fmt.format(**d) of a format string known only when it runs (not the dict's ** that is
# unsupported)
def fill(fmt: str, d: dict[str, int]) -> str:
    return fmt.format(**d)


print(fill("{a}", {"a": 1}))
