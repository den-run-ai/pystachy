# error: the two exception bases of a class must be independent: neither derives from the other
class Base(ValueError):
    pass


class Child(Base):
    pass


class Both(Child, Base):
    pass


raise Both("x")
