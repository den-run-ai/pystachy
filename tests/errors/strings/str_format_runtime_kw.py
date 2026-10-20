# error: str_format_runtime_kw.py:5: error: str.format() of a format string computed at run time is not supported (only of a string literal, "{}".format(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# fmt.format(name=...) of a format string known only when it runs (keyword arguments are not
# what is unsupported)
def greet(fmt: str, who: str) -> str:
    return fmt.format(name=who)


print(greet("hello {name}", "you"))
