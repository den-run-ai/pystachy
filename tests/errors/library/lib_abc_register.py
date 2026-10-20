# error: Shape.register() is not supported: isinstance() and issubclass() of an ABC are decided by the class statements, so no class can become a virtual subclass
from abc import ABC


class Shape(ABC):
    pass


class Other:
    pass


Shape.register(Other)
