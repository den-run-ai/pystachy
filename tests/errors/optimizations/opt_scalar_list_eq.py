# error: cannot compare list[int | None] == list[int]
xs: list[int | None] = [1]
ys: list[int] = [1]
print(xs == ys)
