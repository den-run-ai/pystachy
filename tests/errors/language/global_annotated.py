# error: annotated name 'x' can't be global
x = 1


def f() -> None:
    global x
    x: int = 2
