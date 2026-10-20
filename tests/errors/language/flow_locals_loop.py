# error: expected int, got int | str
# value holds a str or an int (int | str), which f's int return does not take: CPython
# returns the str where the loop runs no iteration.
def f() -> int:
    value = "3"
    for i in range(1):
        value = int(value)
    return value
print(f())
