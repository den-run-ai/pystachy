# error: list_add_nested.py:5: error: unsupported operand types for +: list[list[str]] and list[list[str | None]] (a list holds items of one type)
inner = ["a"]
src = [inner]
other: list[list[str | None]] = [[None]]
both = src + other
both[0].append(None)
print(inner[1].upper())
