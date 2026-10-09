# error: e.__class__ of an exception is not supported; type(e).__name__ is
class E(Exception):
    def __init__(self, x: int):
        super().__init__(x)
        self.x = x

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(x={self.x!r})"


print(repr(E(1)))
