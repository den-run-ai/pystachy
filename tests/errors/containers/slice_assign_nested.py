# error: slice_assign_nested.py:6: error: expected list[list[str | None]], got list[list[str]]
# (the inner lists, shared with src, would take None through dst; CPython runs it)
inner = ["a"]
src = [inner]
dst: list[list[str | None]] = []
dst[:] = src
dst[0].append(None)
print(inner[1].upper())
