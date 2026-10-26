# error: python_int_bool_builtin.py:13: error: expected int, got bool
# pystachy: python-int
# A builtin's name that the program binds (here abs) names no builtin: a bool given to an int
# parameter that the function passes to it is rejected (CPython's abs here returns the bool)
def abs(v: int) -> int:
    return v


def show(x: int) -> None:
    print(abs(x))


show(True)
