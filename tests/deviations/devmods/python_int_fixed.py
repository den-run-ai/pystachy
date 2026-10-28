# A module that does not opt in to promoting ints, whose function takes a 64-bit int
# (tests/deviations/python_int_limits.py).


def doubled(n: int) -> int:
    return n * 2
