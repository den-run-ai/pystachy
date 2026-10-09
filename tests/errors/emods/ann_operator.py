class P:
    def __init__(self) -> None:
        self.v = 1

    def __or__(self, o: int) -> int:
        print("or ran")
        return 1


OBJ = P()


def joined(x: OBJ | int, *rest):
    "CPython calls OBJ.__or__ when the def statement runs"
    return x
