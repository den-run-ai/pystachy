# error: property 'value' of 'C' is read-only
class C:
    @property
    def value(self) -> int:
        return 1

c = C()
c.value += 2
