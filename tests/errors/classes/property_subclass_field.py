# error: conflicts with property 'value'
class C:
    @property
    def value(self) -> int:
        return 1

class D(C):
    value = 2
