# error: unsupported operand types for +: list[list[float]] and list[str] (a list holds items of one type)
# pystachy: dynamic-any
# Float-list aliases remain outside the native int-list boundary.
inner: list[float] = [1.0]
items: list[list[float]] = [inner]
words = ["word"]
print(items + words)
