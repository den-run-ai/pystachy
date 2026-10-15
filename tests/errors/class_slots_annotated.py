# error: field 'x' is outside __slots__ of 'Empty'
class Empty:
    __slots__ = ()
    x: int

    def __init__(self) -> None:
        self.x = 1


print(Empty().x)
