# error: bool_key_store.py:5: error: a bool key is stored into a dict with int keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()
d: dict[int, int] = {1: 1}
print(d[True], True in d)  # (a bool looks up the int key it equals)
del d[True]
d[True] = 2  # (CPython: {True: 2})
print(d)
