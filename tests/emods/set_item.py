class H:
    def __init__(self) -> None:
        self.v = 1

    def __hash__(self) -> int:
        return 1


h = H()


class Table:
    KEYS = {(h, 1)}

    def __init__(self, *a):
        self.a = a
