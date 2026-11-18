# error: overrides of A.v() return incompatible types; use a common return type
class A:
    @property
    def v(self):
        return 1


class B(A):
    @property
    def v(self):
        return "s"


xs: list[A] = [A(), B()]
for x in xs:
    print(x.v)
