# error: python_int_bool_param.py:10: error: expected int, got bool
# pystachy: python-int
# A bool where a promoting int is stored (a return, an annotated variable or field, a parameter that
# the function may show, as here, see docs/python-int.md) is rejected, as in a module that does not
# opt in: CPython keeps the bool, which prints as True
def show(x: int) -> None:
    print(x)


show(True)
