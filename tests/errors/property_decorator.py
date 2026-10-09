# error: unsupported decorator @property
class C:
    def __init__(self) -> None:
        self.x = 1

    @property
    def double(self) -> int:
        return self.x * 2
