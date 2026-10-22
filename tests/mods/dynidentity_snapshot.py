# Deliberately no dynamic-any pragma: a dynamic caller observes these module bindings.
number = int("9000")
saved = 0


def rebind() -> int:
    global number
    number = int("9000")
    return 0


def capture() -> None:
    global saved
    saved, _ = number, rebind()
