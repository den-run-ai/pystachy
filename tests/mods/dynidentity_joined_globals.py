# Typed module: importing it into an opt-in program must retain its global objects.
VALUE: int | float | None = int("1000")


def replace() -> None:
    global VALUE
    VALUE = int("1000")


class Constants:
    LITERAL = 1000
    FLOAT = 1.5
