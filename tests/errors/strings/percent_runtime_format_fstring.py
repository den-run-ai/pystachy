# error: percent_runtime_format_fstring.py:4: error: % formatting with a format string computed at run time is not supported (only of a string literal, "%d" % x, or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
# an f-string on the left is a format string built when it runs (here "%5d|")
w = 5
print(f"%{w}d|" % 3)
