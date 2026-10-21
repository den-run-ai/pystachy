# error: exc_super_classmethod_cls.py:11: error: calling class method B.make() is not supported: it uses cls, and is compiled only for A
class A(Exception):
    @classmethod
    def make(cls, m: str) -> "A":
        return cls(m)


class B(A):
    def again(self) -> str:
        # (CPython's cls is the object's class, B)
        return repr(super().make("x"))


print(B("q").again())
