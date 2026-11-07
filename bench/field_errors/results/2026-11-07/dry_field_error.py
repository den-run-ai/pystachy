class Base:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7
class Child(Base):
    pass

def read(obj: Base) -> int:
    value = None
    print(value)
    value = obj.value
    return value
print(read(Child(True)))
