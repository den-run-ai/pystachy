# A class method of a class template that assigns, through cls, a class attribute that the
# object's class inherits. CPython gives that class an attribute of its own, which is not
# supported: in the class's own copy of the method the store does not compile, so the program is
# compiled without such copies, as before they were made (#1744), and the store changes the
# template's attribute. These programs print what CPython prints that way: the template gets
# the same store too, or the class between them binds the attribute to the value that the
# template's has
class Base:
    count = 0

    def __init__(self, v):
        self.v = v

    @classmethod
    def mark(cls) -> str:
        cls.count = 7
        return "stored"


class Sub(Base):
    pass


s = Sub(2)
b = Base(1)
print(s.mark(), b.mark())
print(Base.count, Sub.count)


class Style:
    count = 0

    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def bump(cls) -> int:
        cls.count += 1
        return cls.count


class Mid(Style):
    count = 0


class Deep(Mid):
    pass


print(Deep(1).bump())
