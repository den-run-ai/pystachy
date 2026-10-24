# error: unsupported operand types for +: list[tuple[int, ...]] and list[str] (a list holds items of one type)
# pystachy: dynamic-any
# Fresh list storage cannot box a typed variadic-tuple leaf yet.
items: list[tuple[int, ...]] = [(1, 2)]
words = ["word"]
print(items + words)
