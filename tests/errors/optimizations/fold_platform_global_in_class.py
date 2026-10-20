# error: fold_platform_global_in_class.py:13: error: a class body may only contain fields, methods, a docstring, pass and ..., not a global statement
# The same for a platform test (fold_typing_global_in_class.py), also one in a branch that runs:
# CPython prints 2 3.
import sys

x = 1
y = 1


class C:
    if sys.platform != "win32":
        if sys.platform == "win32":
            global x
        global y
    x = 2
    y = 3


print(x, y)
