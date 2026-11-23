# A class method of a class template whose cls(...) result, made through an object of a class
# deriving from the template, is kept in a variable that holds a template object afterwards.
# With the class's own copy of the method the result is the class's object and the later store
# does not compile, so the program is compiled without such copies, as before they were made
# (#1744): cls is the template there, and the program prints what CPython prints
class Style:
    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def make(cls, fmt: int):
        return cls(fmt)


class Sub(Style):
    pass


s = Sub(1).make(2)
print(s.fmt)
s = Style(3)
print(s.fmt)
