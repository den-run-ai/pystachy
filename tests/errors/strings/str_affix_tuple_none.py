# error: str_affix_tuple_none.py:4: error: tuple for endswith must only contain str, not NoneType
# (an item that is str | None raises CPython's TypeError when it is reached and is None)
s = "abc"
print(s.endswith(("x", None), 0, 2))
