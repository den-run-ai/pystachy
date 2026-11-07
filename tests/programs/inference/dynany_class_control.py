# Non-opt-in control: the new dynamic representation preserves static reflection.


class Base:
    pass


class Child(Base):
    pass


def check(value: Base) -> None:
    print(type(value).__name__, isinstance(value, Base), type(value) is Base)


check(Base())
check(Child())
print(type(1).__name__, type(1) is int)
print(type(True).__name__, type(True) is bool, type(True) is int)
print(type(None).__name__, type(None) is type(None))
print(isinstance(Base(), Base), isinstance(Child(), Base))
