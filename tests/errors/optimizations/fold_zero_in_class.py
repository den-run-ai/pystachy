# error: fold_zero_in_class.py:5: error: a class body may only contain fields, methods, a docstring, pass and ..., not an if statement
# Nor is "if 0:" in a class body (fold_false_in_class.py), also where its else branch binds the
# class attribute that is read (CPython prints 2).
class C:
    if 0:
        y = 1
    else:
        y = 2


print(C.y)
