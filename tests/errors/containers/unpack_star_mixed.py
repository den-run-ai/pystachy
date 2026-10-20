# error: cannot infer the type of starred target 'rest', a list of str and float items; annotate it (rest: list[str | float])
first, *rest = (1, "x", 2.5)
print(first, rest)
