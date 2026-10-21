# error: str_format_map_args.py:3: error: str.format_map() takes exactly one argument (2 given)
# format_map() of two mappings (CPython's TypeError)
print("{a}".format_map({"a": 1}, {"b": 2}))
