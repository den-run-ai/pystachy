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
class C8(Base):
    pass
class C9(Base):
    pass
class C10(Base):
    pass
class C11(Base):
    pass
class C12(Base):
    pass
class C13(Base):
    pass
class C14(Base):
    pass
class C15(Base):
    pass
class C16(Base):
    pass
class C17(Base):
    pass
class C18(Base):
    pass
class C19(Base):
    pass
class C20(Base):
    pass
class C21(Base):
    pass
class C22(Base):
    pass
class C23(Base):
    pass
class C24(Base):
    pass
class C25(Base):
    pass
class C26(Base):
    pass
class C27(Base):
    pass
class C28(Base):
    pass
class C29(Base):
    pass
class C30(Base):
    pass
class C31(Base):
    pass
def same(a: Base, b: Base) -> bool:
    return a == b
print(same(C0(True), C31(True)))
