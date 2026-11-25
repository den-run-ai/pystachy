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
print(a.default, b.default, Style.default, Sub.default)
Style.reset("^")
print(a.default, b.default, Style.default, Sub.default)
b.reset("&")
print(a.default, b.default, Style.default, Sub.default)
Style.reset("!")
print(a.default, b.default, Style.default, Sub.default)
c = Sub("x")
print(c.default)
