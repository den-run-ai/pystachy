# error: expected str, got int | str
# value holds a str and then an int (int | str), which read()'s str return does not take: CPython's
# read() returns the int.
def f() -> int:
    value = "3"
    def read() -> str:
        return value
    value = int(value)
    print(read())
    return value
print(f())
