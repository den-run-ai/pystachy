class Shape:
    def __init__(self, side: int) -> None:
        self.side = side

    @property
    def area(self):
        return self.side * self.side

    @property
    def name(self):
        return "shape" + str(self.side)
