# an unannotated class attribute (x = 4) is x: T = 4, T given by its value as for a field
class C:
    x = 4
    name = "c"
    ratio = 2.5
    flags = [True]

    @classmethod
    def g(cls) -> int:
        return cls.x * 2

    def h(self) -> str:
        return self.name * self.x


c = C()
print(C.x, C.g(), c.x, c.h(), C.ratio, c.flags, C.name)
C.x = 1
print(C.x, c.x, c.h())
