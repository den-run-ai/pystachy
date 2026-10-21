# A union annotation whose members overlap, a class and classes derived from it, holds what its
# base class holds: Base | Child is Base, and Base | Child | Other is the reference union
# Base | Other, as every Child is a Base (once a compile-time error)
class Base:
    def name(self) -> str:
        return "base"


class Child(Base):
    def name(self) -> str:
        return "child"


class Other:
    def name(self) -> str:
        return "other"


def check(value: Base | Child) -> None:
    print(value.name(), isinstance(value, Child))


def either(value: Base | Child | Other | None) -> str:
    return "none" if value is None else value.name()


check(Child())
check(Base())
print(either(Child()), either(Other()), either(Base()), either(None))
