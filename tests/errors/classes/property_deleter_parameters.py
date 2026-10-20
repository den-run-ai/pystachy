# error: property deleter value must take only self
class C:
    @property
    def value(self) -> int:
        return 1

    @value.deleter
    def value(self, v: int) -> None:
        pass
