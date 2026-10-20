def note(s: str) -> int:
    print("note:", s)
    return 1


class Table:
    width = note("width")

    def __init__(self, *i: int):  # (*args in __init__: a class Pystachy leaves uncompiled)
        self.i = i
