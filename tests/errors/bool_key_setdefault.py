# error: bool_key_setdefault.py:3: error: a bool key is stored into a dict with int keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()
d: dict[int, list[int]] = {}
d.setdefault(False, []).append(1)  # (CPython: {False: [1]})
print(d)
