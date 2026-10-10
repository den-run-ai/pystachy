# error: sum() with a bool start is not supported: it returns the bool for an empty iterable, else a number; use int(start) for a numeric result
values: list[int] = []
start = True
print(sum(values, start))
