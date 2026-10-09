# error: a class body may only contain annotated fields, methods, a docstring, pass and ..., not a try statement
class C:
    try:
        X = int("1")
    except ValueError:
        X = 0


print(C.X)
