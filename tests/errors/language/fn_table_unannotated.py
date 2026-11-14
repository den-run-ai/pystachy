# error: fn_table_unannotated.py:11: error: expected <function add>, got <function sub> (each function is a type of its own: a variable, a list's items or a dict's values hold one function)
# (no annotation gives the Callable that would hold both)
def add(a, b):
    return a + b


def sub(a, b):
    return a - b


ops = [add, sub]
print(ops[0](1, 2))
