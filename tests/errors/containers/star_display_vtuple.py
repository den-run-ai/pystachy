# error: runtime-length tuple elements must be int, float, bool, str or their optional types
rows = [[1], [2]]
print((*rows, [3]))
