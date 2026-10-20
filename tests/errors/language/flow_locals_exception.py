# error: expected int, got int | str
# value holds a str or an int (int | str), which f's int return does not take: CPython
# returns the str where int() raises.
def f() -> int:
    value = "3"
    try:
        value = int(value)
    except ValueError:
        print(value)
    return value
print(f())
