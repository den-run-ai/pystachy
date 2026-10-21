# error: @value.setter on method set_value is not supported
class C:
    @property
    def value(self) -> int:
        return 1

    @value.setter
    def set_value(self, v: int) -> None:
        pass
