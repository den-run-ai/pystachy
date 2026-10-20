# error: fn_value_two.py:10: error: expected <function double>, got <function triple> (each function is a type of its own: a variable, a list's items or a dict's values hold one function)
def double(x: int) -> int:
    return x * 2


def triple(x: int) -> int:
    return x * 3


fs = [double, triple]
