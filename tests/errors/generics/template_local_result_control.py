# error: expected list[float | int], got list[int]
def controlled(n):
    result = [n]
    for item in range(n):
        print(item)
    return result


result: list[int | float] = controlled(1)
