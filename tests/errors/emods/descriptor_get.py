class One:
    def __init__(self) -> None:
        self.n = 0

    def __get__(self, obj: object, typ: object) -> int:
        return 1


class Holder:
    x: One = One()
