# error: assigning class attribute 'default' through Sub, which inherits it from Style, is not supported
# (cls in a class method that Sub inherits from class template Style, called through an object
# of Sub, is Sub: CPython gives Sub an attribute of its own there, as for a class that is no
# template's, where the same store is rejected. Before the object's class had its own copy of
# the method, the store changed Style's, #1744)
class Style:
    default = "%"

    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def reset(cls, to: str) -> None:
        cls.default = to


class Sub(Style):
    pass


a, b = Style(1), Sub(2)
b.reset("&")
print(a.default, b.default, Style.default, Sub.default)
