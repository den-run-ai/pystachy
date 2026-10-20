# error: str_format_map_runtime.py:5: error: str.format_map() of a format string computed at run time is not supported (only of a string literal, "{}".format_map(...), or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# format_map() of a module global that two assignments bind: its format is known only at run time
FMT = "{a}"
FMT = FMT + " {b}"
print(FMT.format_map({"a": 1, "b": 2}))
