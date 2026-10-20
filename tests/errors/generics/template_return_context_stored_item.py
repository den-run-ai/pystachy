# error: expected list[list[int | str]], got list[list[int]]
def fresh(value):
    return [value]


stored = [1]
result: list[list[int | str]] = fresh(stored)
