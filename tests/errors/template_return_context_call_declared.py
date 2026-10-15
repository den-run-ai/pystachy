# error: expected list[list[float | int]], got list[list[int]]
def declared(n) -> list[int]:
    return [n]


def nested(n):
    return [declared(n)]


result: list[list[int | float]] = nested(1)
