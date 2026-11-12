# error: cannot compare type[A] == Tag
# == of a class object and an object whose class defines __eq__ would run that method, reflected,
# with the class object (#7); the object on the left is supported
class A:
    pass


class Tag:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Tag) and other.n == self.n


def same(k: type[A], t: Tag) -> bool:
    return k == t


print(same(A, Tag(1)))
