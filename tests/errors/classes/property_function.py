# error: property() called as a function is not supported: decorate the getter with @property and the setter with @x.setter
class C:
    def __init__(self) -> None:
        self._x = 1

    def get_x(self) -> int:
        return self._x

    def set_x(self, v: int) -> None:
        self._x = v

    x = property(get_x, set_x)


c = C()
c.x = 2
print(c.x)
