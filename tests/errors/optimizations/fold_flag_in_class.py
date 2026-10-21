# error: fold_flag_in_class.py:10: error: a class body may only contain fields, methods, a docstring, pass and ..., not an if statement
# A class body's test of TYPE_CHECKING = False is not decided either (fold_false_in_class.py):
# CPython prints 2.
TYPE_CHECKING = False

x = 1


class C:
    if TYPE_CHECKING:
        global x
    x = 2


print(x)
