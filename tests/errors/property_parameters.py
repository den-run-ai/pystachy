# error: property value must take only self
class C:
    @property
    def value(self, x: int) -> int:
        return 1
