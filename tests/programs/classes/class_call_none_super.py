def argument() -> int:
    print("argument")
    return 7


class Base:
    def value(self, n: int) -> int:
        return n

    @property
    def prop(self) -> int:
        return 11


class Child(Base):
    def value(self, n: int) -> int:
        return super().value(argument())

    def explicit(self) -> int:
        return super(Child, self).value(argument())

    def property_value(self) -> int:
        return super().prop


def absent() -> Child | None:
    return None


for present in [False, True]:
    obj = Child() if present else absent()
    try:
        print("value", Child.value(obj, argument()))
    except AttributeError as error:
        print(str(error))
    try:
        print("explicit", Child.explicit(obj))
    except AttributeError as error:
        print(str(error))
    try:
        print("property", Child.property_value(obj))
    except AttributeError as error:
        print(str(error))
