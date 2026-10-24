# error: unsupported operand types for +: list[tuple[tuple[int, ...],int]] and list[str] (a list holds items of one type)
# pystachy: dynamic-any
# Fixed tuples cannot hide a variadic-tuple leaf from the boxing guard.
variadic: tuple[int, ...] = (1, 2)
items: list[tuple[tuple[int, ...], int]] = [(variadic, 3)]
words = ["word"]
print(items + words)
