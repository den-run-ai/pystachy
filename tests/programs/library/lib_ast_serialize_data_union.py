# ast_serialize.parse()'s last element: the extension's dict holds a str, two bools and two lists,
# by key; the port's holds the union of those types. len() of such a value selects the member
# its tag names, and raises CPython's TypeError for a bool, so this read needs no isinstance()
from ast_serialize import parse

r = parse("m.py", "x = 1\n")
print(len(r[4]["source_hash"]))
try:
    print(len(r[4]["is_partial_package"]))
except TypeError as e:
    print("TypeError", e)
