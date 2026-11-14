# error: fn_table_returns.py:10: error: expected <function add>, got <function name> (each function is a type of its own: a variable, a list's items or a dict's values hold one function)
def add(a: int, b: int) -> int:
    return a + b


def name(a: int, b: int) -> str:
    return str(a + b)


table = {"add": add, "name": name}
