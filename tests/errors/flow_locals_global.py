# error: expected int, got int | str
# The global value holds a str or an int (int | str), which f's int return does not take.
value = "3"
def f() -> int:
    global value
    value = int(value)
    return value
print(f())
