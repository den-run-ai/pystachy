# error: cannot infer the type of field 'extra'
# A failed subclass factory body must not fall back to constructing Base.
class Base:
    def __init__(self, x):
        self.x = x
    @classmethod
    def make(cls, x: int):
        return cls(x)

class Sub(Base):
    def __init__(self, x: str) -> None:
        super().__init__(x)
        self.extra = x + "tail"

s = Sub("head")
try:
    q = s.make(1)
    print("wrong", type(q).__name__, q.x)
except TypeError as exc:
    print(type(exc).__name__, str(exc))
