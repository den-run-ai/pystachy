# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (dict.get() of an int that is not there)
counts = {"a": 1}
v = counts.get("b")
print(v, counts.get("a"))
print(v + 1)
