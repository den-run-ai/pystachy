# error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not float
squares = {x / 2: x for x in range(3)}
print(squares)
