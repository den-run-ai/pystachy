# A.hi(b) of an exception class in a static method (b is not its first parameter, so this is not
# super().hi()): A's method, called on b
class A(Exception):
    def hi(self) -> str:
        return "A:" + str(self)


class B(A):
    @staticmethod
    def make() -> str:
        b = B("q")
        return A.hi(b)


print(B.make())
