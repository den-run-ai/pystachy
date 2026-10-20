# error: get() returns both int and object (each function has one return type)
# a function that returns either the sentinel it was given or another type would need a union of
# the two, which an object() value cannot be part of (#251)
_MISSING = object()


def get(d, k, default=_MISSING):
    if k in d:
        return d[k]
    if default is _MISSING:
        raise KeyError(k)
    return default


print(get({"a": 1}, "a"))
