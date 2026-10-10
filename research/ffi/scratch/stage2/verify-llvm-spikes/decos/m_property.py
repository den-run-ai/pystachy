class C:
    def __init__(self) -> None:
        self.v = 1
    @property
    def p(self) -> int:
        return self.v
print(C().p)
