class C:
    def __init__(self) -> None:
        self.v = 1
    @property
    def p(self) -> int:
        return self.v
    @p.setter
    def p(self, x: int) -> None:
        self.v = x
c = C()
c.p = 3
print(c.p)
