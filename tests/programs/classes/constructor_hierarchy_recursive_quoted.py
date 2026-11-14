class Base:
    pass


class Child(Base):
    def __init__(self, value):
        self.data: int = int(value)
        self.next: "Child | None" = None


value = Child("61")
value.next = value
print(value.data, value.next is value)
