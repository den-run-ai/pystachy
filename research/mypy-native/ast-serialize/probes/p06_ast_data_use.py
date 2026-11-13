# How a program uses parse()'s last element (a dict of bool, str and lists), as mypy's
# nativeparse does: values passed where a str or a bool is expected
from ast_serialize import parse

r = parse("m.py", "x = 1\n")
data = r[4]
h = data["source_hash"]
if isinstance(h, str):
    print(len(h), h[:8])
p = data["is_partial_package"]
print(p is False)
s: str = data["source_hash"]
print(s.upper()[:4])
