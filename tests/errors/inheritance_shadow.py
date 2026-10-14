# error: field 'value' of 'Child' conflicts with method 'Base.value': method and field shadowing in an inheritance hierarchy is not supported
class Base:
    def value(self) -> int:
        return 1


class Child(Base):
    value = 2


print(Child().value())
