# error: a subclass of class template Base with a secondary base is not supported
# A template hierarchy's classes have one base each: the specialization of the class template
# that their objects begin as.
class Base:
    def __init__(self, value):
        self.value = value


class Mixin:
    def hello(self) -> str:
        return "hello"


class Child(Base, Mixin):
    pass


print(Child(1).hello())
