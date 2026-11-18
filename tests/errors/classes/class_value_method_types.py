# error: Base.make() returns int, and Leaf.make() of a class deriving from it str: a call through a class object has one type
# CPython's call returns whatever the method of the class the value is returns (printing 1 one)
class Base:
    @staticmethod
    def make():
        return 1


class Leaf(Base):
    @staticmethod
    def make():
        return "one"


def made(k: type[Base]) -> None:
    print(k.make())


made(Base)
made(Leaf)
