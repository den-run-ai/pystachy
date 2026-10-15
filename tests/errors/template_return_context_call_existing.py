# error: expected list[list[float | int]], got list[list[int]]
def existing(value):
    return value


def nested(value):
    return [existing(value)]


value = [1]
result: list[list[int | float]] = nested(value)
