# error: percent_runtime_format_aug.py:3: error: % formatting with a format string computed at run time is not supported (only of a string literal, "%d" % x, or of a module global that one module-level assignment binds to one, where nothing else in the program binds its name, not even as a local)
s = "%s-%s"
s %= ("a", "b")
print(s)
