# getattr() with a default (#486): the attribute where the object has it, else the default
class C:
    def __init__(self) -> None:
        self.a = 1


print(getattr(C(), "b", 0))
