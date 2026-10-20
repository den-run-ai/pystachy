# error: percent_runtime_format_call.py:7: error: % formatting with a format string computed at run time is not supported (only of a string literal, "%d" % x, or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# a format string a function returns, as a translated message is (gettext)
def tr(s: str) -> str:
    return s


print(tr("%d items") % 3)
