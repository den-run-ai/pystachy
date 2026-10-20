# error: C.f() missing 1 required positional argument: 'x'
class C:
    @classmethod
    def f(cls, x: int) -> int:
        return x


print(C.f())
