# error: dict.update() of a dict[str,int] takes a dict of its type, a list[tuple[str,int]] or keyword arguments, not Generator[tuple[str,int]]
# CPython sets each pair as the generator makes it, which the generator's code could see
d = {"a": 1}
d.update((k, len(d)) for k in "bc")
