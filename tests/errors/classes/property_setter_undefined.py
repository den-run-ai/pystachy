# error: @value.setter needs property value, a @property def value before it in the class body
class C:
    @value.setter
    def value(self, v: int) -> None:
        pass

    @property
    def value(self) -> int:
        return 1
