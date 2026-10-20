# error: argument 1 of show() may be None (str | None), and a test does not narrow a global or a field (a call may change it): copy it to a local variable, and test that
current: str | None = "a"


def show(s: str) -> None:
    print(s)


def report() -> None:
    # a global is not narrowed: a call could change it
    if current is not None:
        show(current)


report()
