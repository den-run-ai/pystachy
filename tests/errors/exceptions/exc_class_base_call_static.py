# error: exc_class_base_call_static.py:12: error: A.hi() is a method of its objects: calling it through the class is not supported
# A.hi(b) in a static method without parameters (b not its first parameter): not super().hi()
class A(Exception):
    def hi(self) -> str:
        return "A:" + str(self)


class B(A):
    @staticmethod
    def make() -> str:
        b = B("q")
        return A.hi(b)


print(B.make())
