# A subclass factory preserves its class when its inferred result location later holds
# a base object too. Both share the existing tagged base layout (#1744).
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
