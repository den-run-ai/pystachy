# error: C.value is a property: read it on an instance
class C:
    @property
    def value(self) -> int:
        return 1

C.value(C())
