class Base:
    def __init__(self, value: int) -> None:
        self.value: int = value

    def get(self) -> int:
        return self.value


class Unused(Base):
    def __init__(self, value):
        self.value: int = int(value)

    def get(self) -> int:
        return self.missing
