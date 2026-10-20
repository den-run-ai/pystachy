# error: dict.fromkeys(keys, None) needs values that can be None
d: dict[str, int] = dict.fromkeys(["a", "b"], None)
