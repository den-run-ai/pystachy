# error: conflicts with property 'value'
class Base:
    value = 2

class C(Base):
    @property
    def value(self) -> int:
        return 1
