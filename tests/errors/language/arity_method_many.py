# error: C.m() takes 2 positional arguments but 3 were given
class C:
    def m(self, x: int) -> int:
        return x


print(C().m(1, 2))
