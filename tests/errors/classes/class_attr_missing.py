# error: type object 'C' has no attribute 'nope'
class C:
    @classmethod
    def f(cls) -> int:
        return cls.nope


print(C.f())
