# error: bool_opt_key_getitem.py:4: error: a bool | None key of a dict with int keys is supported by get() and in only, as CPython's KeyError would name it as the bool it is: test it with 'is not None' first
d: dict[int, str] = {1: "one"}
k: bool | None = False
print(d[k])  # (CPython: KeyError: False)
