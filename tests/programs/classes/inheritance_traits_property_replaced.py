# A trait's property replaces the one of the class it derives from as a whole, as CPython finds
# the property by the method resolution order: the trait's getter alone leaves the class no
# setter or deleter, though the replaced property had them. A class without the trait keeps them.
class Root:
    def __init__(self) -> None:
        self._x = 1

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, v: int) -> None:
        self._x = v

    @x.deleter
    def x(self) -> None:
        self._x = 0


class Primary(Root):
    pass


class Trait(Root):
    @property
    def x(self) -> int:
        return self._x * 10


class Both(Primary, Trait):
    pass


def read(r: Root) -> int:
    return r.x


def write(r: Root, v: int) -> str:
    try:
        r.x = v
        return f"set {r.x}"
    except AttributeError as e:
        return f"AttributeError {e}"


def remove(r: Root) -> str:
    try:
        del r.x
        return f"deleted {r.x}"
    except AttributeError as e:
        return f"AttributeError {e}"


b = Both()
print(b.x, read(b))
try:
    b.x = 7
    print("set", b.x)
except AttributeError as e:
    print("AttributeError", e)
try:
    del b.x
    print("deleted", b.x)
except AttributeError as e:
    print("AttributeError", e)
p = Primary()
p.x = 3
print(p.x, read(p))
del p.x
print(p.x)
print(write(Both(), 7), write(Primary(), 7), remove(Both()), remove(Primary()))
