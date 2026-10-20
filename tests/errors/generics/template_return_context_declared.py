# error: expected list[float | int], got list[int]
def declared(value) -> list[int]:
    return [value]


result: list[int | float] = declared(1)
