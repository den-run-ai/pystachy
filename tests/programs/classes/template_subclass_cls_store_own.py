# A class method of a class template that assigns a class attribute through cls, called through
# an object of a class deriving from the template whose class body binds the attribute again:
# cls is that class, so the store and the read change and find its attribute, not the
# template's, which they did before the class had its own copy of the method (#1744)
class Style:
    default = "%"

    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def reset(cls, to: str) -> None:
        cls.default = to

    @classmethod
    def bump(cls) -> str:
        cls.default = cls.default + "!"
        return cls.default


class Own(Style):
    default = "o"


a, b = Style(1), Own(2)
b.reset("&")
print(a.default, b.default, Style.default, Own.default)
a.reset("#")
print(a.default, b.default, Style.default, Own.default)
print(b.bump(), a.bump(), Style.default, Own.default)
