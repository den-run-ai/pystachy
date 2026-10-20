# error: str_affix_tuple_nested.py:4: error: tuple for startswith must only contain str, not tuple
t = ("x", ("b", "c"))
s = "abc"
print(s.startswith(t))
