# error: ValueError: unsupported format character '%' (0x25) at index 5
# A % right after a mapping key is that conversion's type, which CPython rejects.
d = {"a": 1, "b": 2}
print("[%(a)%(b)s]" % d)
