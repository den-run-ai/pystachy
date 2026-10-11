# error: a generator expression is only supported as the argument of
# CPython sets each pair as the generator makes it, which the generator's code could see
d = {"a": 1}
d.update((k, len(d)) for k in "bc")
