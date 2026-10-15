# error: expected int, got float
def indirect(a, b):
    result = [a, b]
    result.append(a)  # A mutated local is outside fresh-result forwarding.
    return result


result: list[int | float] = indirect(1, 2.5)
