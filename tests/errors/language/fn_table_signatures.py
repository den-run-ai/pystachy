# error: fn_table_signatures.py:11: error: expected <function add>, got <function neg> (each function is a type of its own: a variable, a list's items or a dict's values hold one function)
# (functions of two signatures share no Callable)
def add(a: int, b: int) -> int:
    return a + b


def neg(a: int) -> int:
    return -a


ops = [add, neg]
