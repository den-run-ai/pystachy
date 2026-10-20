# error: overriding 'value' as a different kind of attribute
class C:
    def value(self) -> int:
        return 1

class D(C):
    @property
    def value(self) -> int:
        return 2
