# error: expected int, got int | str
# value holds a str or an int (int | str), which f's int return does not take: CPython
# returns the str where flag is false.
def f(flag: bool) -> int:
    value = "3"
    if flag:
        value = int(value)
    return value
print(f(True))
