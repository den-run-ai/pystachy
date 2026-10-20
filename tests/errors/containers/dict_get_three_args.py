# error: get expected at most 2 arguments, got 3
d: dict[str, str] = {"a": "b"}
print(d.get("a", "c", "d"))
