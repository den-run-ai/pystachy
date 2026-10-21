# error: cannot unpack non-iterable Plain object
class Plain:
    def __init__(self) -> None:
        self.xs = [1, 2]


a, b = Plain()
