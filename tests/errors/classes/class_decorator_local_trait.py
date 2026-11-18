# error: unsupported decorator @trait
# (the program's own function of mypy_extensions' name: CPython calls it on the class)
def trait(cls):
    print("decorating")
    return cls


@trait
class A:
    pass


print(A())
