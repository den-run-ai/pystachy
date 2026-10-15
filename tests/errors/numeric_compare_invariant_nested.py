# error: expected list[int], got list[float]
ints = [[1, 2]]
floats = [[1.0, 2.0]]
print(ints == floats)
ints.append(floats[0])
