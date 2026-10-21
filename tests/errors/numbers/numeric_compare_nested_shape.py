# error: cannot compare list[list[int]] == list[tuple[float]]
ints = [[1]]
floats = [(1.0,)]
print(ints == floats)
