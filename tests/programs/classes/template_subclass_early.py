# A specialization of a class template named by an annotation before a subclass's class
# statement: its subclasses' specializations are made once their classes are declared (#962).
class Box[T]:
    kind = "plain"

    def __init__(self, value: T) -> None:
        self.value = value

    def get(self) -> T:
        return self.value

    def label(self) -> str:
        return "box"


def show(b: Box[int]) -> str:
    return b.label() + " " + str(b.get()) + " " + b.kind


class Sub(Box):
    kind = "sub"

    def label(self) -> str:
        return "sub"


print(show(Box(1)), show(Sub(2)))
print(Sub("s").label(), Sub("s").kind, Box("t").kind)
