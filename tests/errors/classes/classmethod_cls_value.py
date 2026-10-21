# error: class 'C' cannot be used as a value
class C:
    @classmethod
    def kind(cls) -> str:
        k = cls
        return "C"


print(C.kind())
