# error: expected list[float | int], got list[int]
def observe(value):
    return len(value)


def escaped(n):
    result = [n]
    size = observe(result)
    return result


result: list[int | float] = escaped(1)
