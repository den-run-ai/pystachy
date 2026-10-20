# error: 'Base' object has no attribute 'extra'
class Base:
    pass


class Child(Base):
    def __init__(self) -> None:
        self.extra = 1


def test(obj: Base) -> None:
    def replace() -> None:
        nonlocal obj
        obj = Base()

    if isinstance(obj, Child):
        replace()
        print(obj.extra)


test(Child())
