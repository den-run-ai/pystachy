# error: str_format_class_value.py:3: error: str.format as a value is not supported: call it, "...".format(...) or str.format("...", ...) of a string literal (map() takes "...".format)
# str.format as map()'s function: each format string is known only when it runs
print(list(map(str.format, ["<{}>", "[{}]"], [1, 2])))
