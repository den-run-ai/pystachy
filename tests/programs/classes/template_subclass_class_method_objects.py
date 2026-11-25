# Subclass factories and builtin-subclass comparisons preserve both class identities,
# including when a factory result shares an inferred location with a base object (#1744/#1739).
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
