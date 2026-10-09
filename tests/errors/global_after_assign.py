# error: name 'x' is assigned to before global declaration
x = 1


def f() -> None:
    x = 5
    global x
