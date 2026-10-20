# error: expected list[float | int], got list[int]
def existing(value):
    return value


value = [1]
result: list[int | float] = existing(value)
