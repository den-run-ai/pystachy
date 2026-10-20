# error: generic_pep695_base.py:8: error: a generic class (class C[T]) with a base class is not supported
class Base:
    def hello(self) -> str:
        return "hi"


# (as class Box(Base, Generic[T]) is not: a generic class's one base is Generic[...])
class Box[T](Base):
    def __init__(self, item: T) -> None:
        self.item = item


print(Box(1).hello())
