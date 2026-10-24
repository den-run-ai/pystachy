# error: unsupported operand types for +: list[list[int]] and list[str] (a list holds items of one type)
# pystachy: dynamic-any
# Boxing an inner typed list must not copy or reinterpret its mutable storage.
inner: list[int] = [1]
items: list[list[int]] = [inner]
words = ["word"]
print(items + words)
