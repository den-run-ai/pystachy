# error: expected int, got float
def pair(a, b):
    return [a, b]


contextual: list[int | float] = pair(1, 2.5)
print(pair(1, 2.5))
