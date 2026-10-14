# error: field 'value' of 'Child' conflicts with method 'Child.value': method and field shadowing in an inheritance hierarchy is not supported
class Base:
    def __init__(self) -> None:
        self.value = 1


class Child(Base):
    def value(self) -> int:
        return 2


print(Child().value())
