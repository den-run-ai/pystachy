# error: a subclass of class template Base with a decorator is not supported
# A decorator may replace the class its statement makes, or change what its methods do, which
# the specializations of the class template its objects belong to would not see.
registry: list[str] = []


def register(cls):
    registry.append(cls.__name__)
    return cls


class Base:
    def __init__(self, value):
        self.value = value


@register
class Child(Base):
    def twice(self) -> int:
        return self.value * 2


print(registry, Child(1).twice())
