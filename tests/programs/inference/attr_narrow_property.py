# A property's read is a call: the second read gives the str, which has no + with an int.
class Ref:
    def __init__(self) -> None:
        self.reads = 0

    @property
    def value(self) -> int | str:
        self.reads += 1
        return 1 if self.reads == 1 else "text"


def bump(e: Ref) -> int:
    if isinstance(e.value, int):
        return e.value + 1
    return 0


print(bump(Ref()))
