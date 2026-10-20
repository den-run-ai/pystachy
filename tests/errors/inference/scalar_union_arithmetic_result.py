# error: expected int, got float | int
def add(value: int | float) -> int:
    return value + 1
print(add(3))
