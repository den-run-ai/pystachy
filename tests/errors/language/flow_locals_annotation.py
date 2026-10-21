# error: expected str, got int
def f() -> int:
    value: str = "3"
    value = int(value)
    return value
print(f())
