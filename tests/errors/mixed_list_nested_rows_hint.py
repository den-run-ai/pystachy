# error: this list literal needs list[tuple[str,tuple[int | float,int | str]]]
print([("a", (1, "x")), ("b", (2.5, 2))])
