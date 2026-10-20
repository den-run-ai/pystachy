# error: list_extend_nested.py:5: error: expected list[list[str | None]], got list[list[str]]
inner = ["a"]
src = [inner]
dst: list[list[str | None]] = []
dst.extend(src)
dst[0].append(None)
print(inner[1].upper())
