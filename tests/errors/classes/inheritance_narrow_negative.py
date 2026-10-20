# error: 'Base' object has no attribute 'extra'
class Base:
    pass


class Child(Base):
    def __init__(self) -> None:
        self.extra = 1


def test(obj: Base) -> None:
    if isinstance(obj, Child):
        return
    print(obj.extra)


test(Base())
