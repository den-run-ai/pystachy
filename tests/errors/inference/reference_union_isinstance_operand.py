# error: runtime reference union isinstance() requires valid type operands
class Base:
    pass


class Child(Base):
    pass


class Other:
    pass


class OtherChild(Other):
    pass


def check(value: Base | Other) -> bool:
    return isinstance(value, (Child, 5))


print(check(Base()))
