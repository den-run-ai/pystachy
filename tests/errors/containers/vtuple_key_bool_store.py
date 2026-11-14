# error: vtuple_key_bool_store.py:5: error: a tuple[bool,int] key is stored into a dict with tuple[int, ...] keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()
# a bool stored where a runtime-length tuple key holds ints is rejected, as for a fixed tuple's:
# CPython keeps the key it adds, which prints as True, not 1
d: dict[tuple[int, ...], str] = {}
d[(True, 1)] = "x"
print(d)
