# error: cannot compare list[int] == list[int | None]
ints = [1]
optional: list[int | None] = [1, None]
print(ints == optional)
