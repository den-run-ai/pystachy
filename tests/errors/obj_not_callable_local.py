# error: 'list' object is not callable
def f() -> None:
    xs = [1]
    xs()


f()
