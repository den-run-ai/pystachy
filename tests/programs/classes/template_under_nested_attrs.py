# Class attributes of an ordinary class that hold an enum member and a nested class (#962), read
# through objects of a class template's specializations under it and through the template's name.
from enum import Enum


class Color(Enum):
    RED = 1
    BLUE = 2


class Base:
    favorite = Color.BLUE

    class Meta:
        kind = "meta"

    def __init__(self) -> None:
        self.n = 0

    def tone(self) -> str:
        return self.favorite.name + " " + self.Meta.kind


class T(Base):
    def __init__(self, item):
        super().__init__()
        self.item = item


xs: list[Base] = [Base(), T(1), T("s")]
for x in xs:
    print(x.tone(), x.favorite is Color.BLUE, x.Meta.kind)
print(T.favorite, T.Meta.kind, T(2).Meta.kind)
