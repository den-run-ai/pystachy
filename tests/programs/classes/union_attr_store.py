# o.x = v where o is a closed union of classes: each class's field or property setter, and the
# errors CPython raises: None's, a frozen dataclass's and a class with only __slots__ (whose
# objects take no new attribute), each with CPython's message
from dataclasses import dataclass


class Plain:
    def __init__(self) -> None:
        self.x = 1


class Prop:
    def __init__(self) -> None:
        self.saved = 2

    @property
    def x(self) -> int:
        return self.saved

    @x.setter
    def x(self, value: int) -> None:
        print("setter", value)
        self.saved = value


@dataclass(frozen=True)
class Frozen:
    x: int


class Slotted:
    __slots__ = ("y",)

    def __init__(self) -> None:
        self.y = 3


def pick(flag: int) -> Plain | Prop | Frozen | Slotted | None:
    if flag == 0:
        return Plain()
    if flag == 1:
        return Prop()
    if flag == 2:
        return Frozen(4)
    if flag == 3:
        return Slotted()
    return None


for i in range(5):
    o = pick(i)
    try:
        o.x = 10 + i
        print("stored", i)
    except AttributeError as e:
        print("AttributeError", e)
    except Exception as e:
        print(type(e).__name__, e)


def both(flag: int) -> Plain | Prop:
    return Plain() if flag == 0 else Prop()


for i in range(2):
    p = both(i)
    p.x += 5
    print(p.x)
