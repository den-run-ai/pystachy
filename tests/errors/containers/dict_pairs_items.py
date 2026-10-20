# error: dict() of a list[int] is not supported: it takes a dict, or (key, value) tuples
# (CPython raises TypeError: cannot convert dictionary update sequence element #0 to a sequence)
print(dict([1, 2]))
