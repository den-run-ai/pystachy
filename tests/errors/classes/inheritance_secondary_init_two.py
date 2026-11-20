# error: both bases declare method '__init__'
# Where neither the class nor its primary chain defines __init__, CPython's method resolution
# order takes the first secondary base's: two of them define one (not supported)
class Base:
    pass


class Sized:
    def __init__(self, size: int) -> None:
        self.size = size


class Named:
    def __init__(self, name: str) -> None:
        self.name = name


class File(Base, Sized, Named):
    pass


print(File(3).size)
