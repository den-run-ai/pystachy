# error: expected list[float | int], got list[int]
def rebound(n):
    result = [n]
    alias = result
    result = [n]
    return alias


result: list[int | float] = rebound(1)
