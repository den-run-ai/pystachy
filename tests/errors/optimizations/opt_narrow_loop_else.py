# error: argument 1 of keep() may be None (str | None); test it with 'is not None' first
def keep(s: str) -> str:
    return s


def f(x: str | None) -> None:
    i = 0
    while i < 5:
        break
    else:
        x = "e"
    print(keep(x))  # the break skips the else block: x may be None here


f(None)
