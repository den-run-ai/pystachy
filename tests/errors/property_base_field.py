# error: conflicts with read-only property 'value'
class Base:
    value = 2

class C(Base):
    @property
    def value(self) -> int:
        return 1
