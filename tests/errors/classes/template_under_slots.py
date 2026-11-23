# error: template_under_slots.py:15: error: inheritance with generic class templates is not supported
# A class template is supported under an ordinary class (#962), not under one that declares
# __slots__ (nor one with a secondary base, __init_subclass__ or __class_getitem__, or a class
# that derives from such a one): its specializations would begin as its objects do otherwise.
class Base:
    __slots__ = ("n",)

    def __init__(self) -> None:
        self.n = 0

    def count(self) -> int:
        return self.n


class Item(Base):
    def __init__(self, value):
        super().__init__()
        self.value = value


print(Item(3).count())
