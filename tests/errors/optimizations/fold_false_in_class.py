# error: fold_false_in_class.py:9: error: a class body may only contain fields, methods, a docstring, pass and ..., not an if statement
# "if False:" is decided only outside class bodies: a global statement in its branch still holds
# for the whole class body, so x = 2 binds the module's x and CPython prints 2. The if statement
# stays, and a class body may not hold one.
x = 1


class C:
    if False:
        global x
    x = 2


print(x)
