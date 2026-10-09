# error: get_none_int.py:3: error: dict.get(key, None) needs values that can be None (str, list, dict, tuple or objects), not int: give another default (int | None would need boxing)
d = {(1, "a"): 1}
print(d.get((1, "a"), None))
