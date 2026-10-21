# error: dict.fromkeys(keys) needs the type of the dict it makes, whose values are None: annotate it (d: dict[K, V | None] = ...)
d = dict.fromkeys(["a", "b"])
