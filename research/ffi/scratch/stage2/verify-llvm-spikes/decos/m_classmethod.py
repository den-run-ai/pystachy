class C:
    @classmethod
    def f(cls, x: int) -> int:
        return x
print(C.f(1))
