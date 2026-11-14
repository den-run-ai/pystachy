from typing import Optional


class Base:
    def score(self) -> int:
        return 0


class Child(Base):
    def __init__(self, value):
        self.data: int = int(value)
        self.next: Optional[Child] = None

    def score(self) -> int:
        return self.data


class Dormant(Child):
    def score(self) -> int:
        return self.missing()
