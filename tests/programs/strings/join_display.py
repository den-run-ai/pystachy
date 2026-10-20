# Displays of items of several scalar types: lists and dicts of their union, as if annotated.
xs = [1, 2.5, 3]
print(xs, xs[0] + xs[1])
rows = [("a", 1), ("b", 2.5)]
print(rows, rows[1][1] * 2)
data = {"name": "x", "count": 3}
print(data["name"], data["count"], data)
mixed = [1, "two", 3.0, None, True]
print(mixed, len(mixed))
