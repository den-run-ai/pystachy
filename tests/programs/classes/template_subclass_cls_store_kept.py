# Inherited cls stores create subclass attributes, while a base store creates its own.
# These equal-value cases already matched CPython before #1744 was fixed and must stay so.
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
