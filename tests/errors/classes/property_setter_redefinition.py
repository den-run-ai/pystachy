# error: redefinition of method 'C.value' is not supported
class C:
    @property
    def value(self) -> int:
        return 1

    @value.setter
    def value(self, v: int) -> None:
        pass

    @value.setter
    def value(self, v: int) -> None:
        pass
