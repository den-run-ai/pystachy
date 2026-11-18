# error: secondary base method 'make' needs a matching instance method signature
# An override of a secondary base's method returns what the base's returns, or a class that
# derives from it: an unrelated class is no Shape where a Shape is expected.
class Shape:
    pass


class Other:
    pass


class Maker:
    def make(self) -> Shape:
        return Shape()


class Base:
    pass


class Impl(Base, Maker):
    def make(self) -> Other:
        return Other()


print(type(Impl().make()).__name__)
