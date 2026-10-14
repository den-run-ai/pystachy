A = 22


def value() -> int:
    return A


class Box:
    value: int

    def __init__(self, value: int):
        self.value = value
