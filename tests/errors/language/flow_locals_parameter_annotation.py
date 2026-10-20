# error: expected str, got int
def f(value: str) -> int:
    value = int(value)
    return value
print(f("3"))
