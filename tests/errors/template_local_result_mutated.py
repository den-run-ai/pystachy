# error: expected list[float | int], got list[int]
def mutated(n):
    result = [n]
    result.append(n)
    return result


result: list[int | float] = mutated(1)
