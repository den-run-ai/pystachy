# A program in which a class under a class template cannot have its own copy of a class method
# (what cls(...) makes is stored where a template's object is stored too, #1744) and that
# compares an object of a class deriving from list with another class's object (#1739): the
# program is compiled without the copies, and the comparison still hands its method the object
# itself, not the list
class Stack(list[int]):
    pass


class Probe:
    def __eq__(self, other: object) -> bool:
        print("Probe.__eq__", type(other).__name__)
        return isinstance(other, Stack)


class Style:
    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def make(cls, fmt: int):
        return cls(fmt)


class Sub(Style):
    pass


print(Probe() == Stack())
s = Sub(1).make(2)
s = Style(3)
print(s.fmt)
