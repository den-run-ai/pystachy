# error: @Other.value.setter is not supported here: Other must be the base class whose property value this class inherits
class Other:
    @property
    def value(self) -> int:
        return 1


class Base:
    @property
    def value(self) -> int:
        return 2


class C(Base):
    @Other.value.setter
    def value(self, v: int) -> None:
        pass
