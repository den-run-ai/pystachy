# error: get expected at most 2 arguments, got 3
d: dict[str, int] = {"a": 1}
print(d.get("a", 5, None))
