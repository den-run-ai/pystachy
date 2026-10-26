# error: python_int_bool_join.py:7: error: expected bool, got int
# pystachy: python-int
# A conditional expression (also and, or) of a bool and a promoting int is rejected, as one of a bool
# and an int is in a module that does not opt in: CPython gives the bool, which prints as True
def pick(c: bool, n: int) -> None:
    m = n * 2
    print(True if c else m)


pick(True, 5)
