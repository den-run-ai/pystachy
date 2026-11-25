# A program whose list subclass object cannot reach Typed.__eq__ as itself (its parameter is
# annotated list[int] | None) and whose class under a class template has its own copy of a class
# method. The comparison ends the trial; the copies alone compile, so the program is compiled
# with them and without the objects, whichever of the two its code reaches
# first (#1744, #1739). Here the comparison comes first; template_subclass_class_method_copy_first.py
# makes the copy first
class Stack(list[int]):
    pass


class Typed:
    def __eq__(self, other: list[int] | None) -> bool:
        print("Typed.__eq__", other)
        return True


class Style:
    tag = "base"

    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def name(cls) -> str:
        return cls.__name__ + cls.tag


class Sub(Style):
    tag = "sub"


s = Stack()
s.append(1)
print(Typed() == s)
print(Sub(1).name())
