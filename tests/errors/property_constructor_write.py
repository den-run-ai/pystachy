# error: conflicts with read-only property 'value'
class C:
    @property
    def value(self) -> int:
        return 1

    def __init__(self) -> None:
        self.value = 2
