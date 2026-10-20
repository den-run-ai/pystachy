# error: sum() with a bool start is not supported: it returns the bool for an empty iterable, else a number; use int(start) for a numeric result
print(sum((x for x in range(3)), True))
