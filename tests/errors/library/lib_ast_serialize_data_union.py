# error: lib_ast_serialize_data_union.py:8: error: unsupported call len(bool | list[tuple[int,list[str]]] | list[tuple[int,str]] | str)
# ast_serialize.parse()'s last element: the extension's dict holds a str, two bools and two lists,
# by key; the port's holds the union of those types, which a value must be narrowed from with
# isinstance() in a function before a str operation
from ast_serialize import parse

r = parse("m.py", "x = 1\n")
print(len(r[4]["source_hash"]))
