# error: bool_key_augassign.py:4: error: a bool key is stored into a dict with int keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()
d: dict[int, int] = {1: 1}
if True in d:
    d[True] += 1  # (it adds True where the right operand deletes the key 1)
print(d)
