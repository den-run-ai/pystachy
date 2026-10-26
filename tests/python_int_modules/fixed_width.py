# A module that does not opt in: its ints are checked 64-bit values.
def scale(x: int, k: int) -> int:
    return x * k


def first_digit(x: int) -> int:
    while x >= 10:
        x //= 10
    return x
