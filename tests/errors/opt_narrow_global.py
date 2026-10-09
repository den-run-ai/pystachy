# error: argument 1 of show() may be None (str | None); test it with 'is not None' first
current: str | None = "a"


def show(s: str) -> None:
    print(s)


def report() -> None:
    # a global is not narrowed: a call could change it
    if current is not None:
        show(current)


report()
