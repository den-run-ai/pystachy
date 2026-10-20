# error: 'Base' object has no attribute 'extra'
class Base:
    pass


class Child(Base):
    def __init__(self) -> None:
        self.extra = 1


class Box:
    def __init__(self, item: Base) -> None:
        self.item = item


def replace(box: Box) -> None:
    box.item = Base()


def test(box: Box) -> None:
    if isinstance(box.item, Child):
        replace(box)
        print(box.item.extra)


test(Box(Child()))
