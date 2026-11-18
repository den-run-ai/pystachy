class Base:
    def score(self) -> int:
        return 0


class Child(Base):
    def __init__(self, value):
        self.data: int = int(value)
        self.next: Child | None = None

    def score(self) -> int:
        return self.data


def score(value: Base) -> int:
    return value.score()


first = Child("41")
second = Child(42)
first.next = second
print(score(first), first.next.score(), first.next is second)
second.next = first
print(second.next is first, type(first) is type(second), isinstance(first, Base))
