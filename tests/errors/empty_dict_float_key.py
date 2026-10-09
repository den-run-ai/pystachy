# error: empty_dict_float_key.py:7: error: dict keys must be int or str
# An empty dict printed before the store that types it: the key type is the store's error, not
# the print's, also when the look-ahead finds the store.
def f() -> None:
    d = {}
    print(d)
    d[1.5] = "a"
    print(d)


f()
