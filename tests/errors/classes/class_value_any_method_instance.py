# error: make through a class object that may be any class's (type[object]) is not supported: in class C it is no class method or static method
class A:
    @classmethod
    def make(cls) -> str:
        return "a"


class C:
    def make(self) -> str:
        return "c"


ks: list[type] = [A, C]
print(ks[0].make())
