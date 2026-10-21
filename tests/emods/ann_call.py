def note(s):
    print("note", s)
    return int


def unused(x: note("annotation")) -> None:
    pass
