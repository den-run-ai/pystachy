# error: python_int_bool_bitwise.py:9: error: expected int, got bool
# pystachy: python-int
# & | ^ of two bools give a bool (True & True is True): a bool given to an int parameter that the
# function so combines with another than an int literal is rejected
def both(x: int, y: int) -> None:
    print(x & y)


both(True, True)
