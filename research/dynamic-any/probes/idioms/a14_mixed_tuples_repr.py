# pystachy: dynamic-any
# #485 10d: repr of a list of tuples of different shapes
rows = [(1, "a", 2.0), ("b", 3, None), ([1, 2], {"k": 1}, (4,))]
print(rows)
print(repr(rows[2]), len(rows[1]))
