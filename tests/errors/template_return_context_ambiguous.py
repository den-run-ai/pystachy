# error: expected int, got float
def pair(a, b):
    return [a, b]


result: list[int | float] | list[int | float | str] = pair(1, 2.5)
