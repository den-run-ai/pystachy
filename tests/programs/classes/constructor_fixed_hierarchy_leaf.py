class Base:
    def get(self) -> int:
        return 0


class Child(Base):
    def __init__(self, value):
        self.value: int = int(value)

    def get(self) -> int:
        return self.value


print(Child(1).get())
