# error: list_iadd_nested.py:5: error: expected list[list[str | None]], got list[list[str]]
inner = ["a"]
src = [inner]
dst: list[list[str | None]] = [[None]]
dst += src
dst[1].append(None)
print(inner[1].upper())
