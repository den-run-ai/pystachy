# error: sequence patterns require a fixed tuple subject, got list[int]
def choose(value: list[int]) -> int:
    match value:
        case [one, two]:
            return one + two
    return 0


print(choose([1, 2]))
