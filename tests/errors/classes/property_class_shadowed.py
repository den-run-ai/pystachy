# error: unsupported decorator @property: the name is shadowed in the class body
class C:
    property = 3
    @property
    def value(self) -> int:
        return 1
