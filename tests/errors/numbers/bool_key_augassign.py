# error: bool_key_augassign.py:9: error: a bool key is stored into a dict with int keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()
def drop(d: dict[int, int]) -> int:
    d.clear()
    return 1


d: dict[int, int] = {1: 1}
if True in d:
    d[True] += drop(d)  # (CPython: {True: 2}: it adds True, as the right operand deleted the key 1)
print(d)
