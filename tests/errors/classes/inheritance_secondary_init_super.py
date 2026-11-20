# error: secondary base methods may not use super() or read or write the instance
# A secondary base's __init__ that calls super().__init__() reaches the next class of the combining
# class's method resolution order, which depends on that class: not supported
class Base:
    def __init__(self) -> None:
        self.base = 1


class Sized:
    def __init__(self, size: int) -> None:
        super().__init__()
        self.size = size


class File(Base, Sized):
    def __init__(self, size: int) -> None:
        Base.__init__(self)
        Sized.__init__(self, size)


print(File(3).size)
