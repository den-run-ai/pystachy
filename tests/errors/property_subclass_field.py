# error: conflicts with read-only property 'value'
class C:
    @property
    def value(self) -> int:
        return 1

class D(C):
    value = 2
