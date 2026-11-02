# a module whose tuple constants equal the importing case's (tuple_constant_modules)
def origin() -> tuple[int, int]:
    return (0, 0)


def empty() -> tuple[()]:
    return ()


def label() -> tuple[str, int]:
    return ("origin", 0)
