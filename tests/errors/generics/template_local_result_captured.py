# error: expected list[float | int], got list[int]
def captured(n):
    result = [n]
    hold = lambda: result
    return result


result: list[int | float] = captured(1)
