# error: expected list[float | int], got list[int]
def existing(value):
    return value


def forwarded(value):
    result = existing(value)
    alias = result
    return alias


result: list[int | float] = forwarded([1])
