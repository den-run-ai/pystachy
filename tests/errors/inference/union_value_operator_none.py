# error: unsupported operand type(s) for +: float | int and str (no member of the closed union supports it)
# Every member's + with a str raises TypeError: an error, as int + str is.
def join(x: int | float) -> str:
    return x + "a"


print(join(1))
