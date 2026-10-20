# error: argument 1 of show() may be None (str | None); test it with 'is not None' first
def show(s: str) -> None:
    print(s)


def report(x: str | None, y: str | None) -> None:
    if x is not None:
        show(x)
        x = y
        show(x)


report("a", None)
