# error: runtime-length tuple elements must be int, float, bool, str or their optional types
print(tuple(enumerate("ab")))
