# error: python_int_bool_min.py:6: error: expected bool, got int
# pystachy: python-int
# min() and max() of a bool and a promoting int are rejected, as of a bool and an int in a module
# that does not opt in: CPython gives the bool, which prints as True
def least(c: bool, n: int) -> None:
    print(min(c, n * 2))


least(True, 5)
