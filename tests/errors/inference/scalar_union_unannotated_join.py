# error: expected int, got int | str
# value holds an int or a str (int | str), which the int return does not take: CPython
# returns the str.

def unsupported(flag: bool) -> int:
    value = 1
    if flag:
        value = "a"
    return value

print(unsupported(True))
