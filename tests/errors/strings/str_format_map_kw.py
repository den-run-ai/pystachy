# error: str_format_map_kw.py:3: error: str.format_map() takes no keyword arguments
# format_map() takes the mapping alone (CPython's TypeError)
print("{a}".format_map(a=1))
