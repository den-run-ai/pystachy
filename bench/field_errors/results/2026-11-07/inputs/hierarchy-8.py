class Base:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7
    def __eq__(self, other: 'Base') -> bool:
        return self.value == other.value
class C0(Base):
    pass
class C1(Base):
    pass
class C2(Base):
    pass
class C3(Base):
    pass
class C4(Base):
    pass
class C5(Base):
    pass
class C6(Base):
    pass
class C7(Base):
    pass
def same(a: Base, b: Base) -> bool:
    return a == b
print(same(C0(True), C7(True)))
