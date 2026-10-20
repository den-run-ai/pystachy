# error: exc_super_static_base.py:11: error: A.st() missing 1 required positional argument: 'x'
class A(Exception):
    @staticmethod
    def st(x: "A") -> str:
        return "A.st " + str(x)


class B(A):
    def inst(self) -> str:
        # super() passes no object to a static method of the base: CPython raises TypeError
        return super().st()


print(B("q").inst())
