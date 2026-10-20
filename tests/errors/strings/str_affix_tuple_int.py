# error: str_affix_tuple_int.py:5: error: tuple for startswith must only contain str, not int
# CPython raises this TypeError at the first item that is no str, if no item before it matches:
# Pystachy rejects such a tuple, whose items have static types
s = "abc"
print(s.startswith(("x", 1)))
