# error: @value.deleter needs property value
class C:
    def value(self) -> int:
        return 1

    @value.deleter
    def value(self) -> None:
        pass
