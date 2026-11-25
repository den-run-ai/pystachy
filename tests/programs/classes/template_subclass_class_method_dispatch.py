from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    limit = 0

    def __init__(self, item: T):
        self.item = item

    @classmethod
    def bump(cls) -> str:
        cls.limit += 1
        return cls.__name__

    @classmethod
    def read(cls) -> str:
        return cls.__name__ + str(cls.limit)


class IntBox(Box[int]):
    pass


class Child(IntBox):
    pass


base = Box(1)
a = IntBox(2)
b = Child(3)
xs = [base, a, b]
for item in xs:
    print(item.read())
    print(item.bump())
    print(item.limit)
print(Box.limit, IntBox.limit, Child.limit)
for item in xs:
    print(item.read(), item.limit)
