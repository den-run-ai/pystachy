# A PEP 695 generic class may name an ordinary base, as class Box(Base, Generic[T]) may: its
# specializations derive from it (tests/programs/classes/generic_bases.py)
class Base:
    def hello(self) -> str:
        return "hi"


class Box[T](Base):
    def __init__(self, item: T) -> None:
        self.item = item


print(Box(1).hello())
