# error: property setter value must take only self and the value, by position
class C:
    @property
    def value(self) -> int:
        return 1

    @value.setter
    def value(self, *, v: int) -> None:
        pass


C().value = 2
