# error: expected int, got str (perhaps because dict() at line 3 of tuples of 3 items makes only an empty dict, taken as dict[int,int]: give it a type first, as in d: dict[K, V] = dict(...))
xs: list[tuple[int, int, int]] = []
d = dict(xs)
d["a"] = 1
