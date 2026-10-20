# Global type inference must not wake an incompatible, unused inherited constructor.
class Base(Exception):
    @staticmethod
    def get(x: int) -> int:
        return x

    @classmethod
    def make(cls) -> 'Base':
        cls.get(1)
        return cls('base')


class Sub(Base):
    def __init__(self, a: int, b: int) -> None:
        super().__init__('sub')


cls = []
print(cls)


class Fill:
    @staticmethod
    def fill() -> None:
        cls.append(1)
