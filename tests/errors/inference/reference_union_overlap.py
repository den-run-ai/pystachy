# error: reference unions cannot contain overlapping class families
class Base:
    pass


class Child(Base):
    pass


def check(value: Base | Child) -> None:
    pass


check(Child())
