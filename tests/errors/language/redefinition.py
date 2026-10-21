# error: redefinition of 'f' is not supported
def f() -> int:
    return 1


print(f())


def f() -> int:
    return 2
