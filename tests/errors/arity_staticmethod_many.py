# error: C.s() takes 1 positional argument but 2 were given
class C:
    @staticmethod
    def s(x: int) -> int:
        return x


print(C.s(1, 2))
