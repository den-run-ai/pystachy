# error: str_format_unbound_kw.py:4: error: str.format() of a format string computed at run time is not supported (only of a string literal, "{}".format(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# str.format(fmt, k=v) through the class, of a format string known only when it runs
def show(fmt: str, x: int) -> str:
    return str.format(fmt, x=x)


print(show("{x:>4}", 1))
