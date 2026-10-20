# error: unsupported decorator @value.getter
class C:
    @property
    def value(self) -> int:
        return 1

    @value.getter
    def value(self) -> int:
        return 2
