# error: name 'x' is used prior to global declaration
x = 1


def f() -> None:
    print(x)
    global x
