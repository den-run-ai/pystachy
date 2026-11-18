# error: set_none_lookup_type.py:4: error: a str is looked up among keys that are always None: only None is one
# (CPython: False; as 1 in {"a"} is rejected, whose key no element's type holds)
s: set[None] = {None}
print("a" in s)
