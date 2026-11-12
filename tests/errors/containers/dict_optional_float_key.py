# error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not float | None
# (a key may be None, or a key type | None; a float is no key type)
d: dict[float | None, int] = {}
print(d)
