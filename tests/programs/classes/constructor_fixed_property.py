class Box:
    def __init__(self, value):
        self.x: int = value

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, value):
        self._x = value


print(Box(7).x)
