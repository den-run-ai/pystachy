READY = "ready"


class Box[T]:
    def __init__(self, item: T) -> None:
        self.item = item

    def __repr__(self) -> str:
        return READY


def show(box: Box[int]) -> None:
    print(box)


show(Box(1))
READY = "changed"
show(Box(2))
