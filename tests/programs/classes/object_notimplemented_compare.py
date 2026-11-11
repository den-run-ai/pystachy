from types import NotImplementedType


class Equal:
    def __init__(self, name: str, accept: bool) -> None:
        self.name = name
        self.accept = accept

    def __eq__(self, other: object) -> bool | NotImplementedType:
        print("eq", self.name)
        if self.accept:
            return True
        return NotImplemented

    def __lt__(self, other: object) -> bool | NotImplementedType:
        print("lt", self.name)
        if self.accept:
            return False
        return NotImplemented

    def __gt__(self, other: object) -> bool | NotImplementedType:
        print("gt", self.name)
        if self.accept:
            return True
        return NotImplemented


a = Equal("a", False)
b = Equal("b", True)
c = Equal("c", False)
print(a == b, a != b, a < b, b > a)
print(a == c, a != c, a == a, a != a)
try:
    print(a < c)
except TypeError as error:
    print(error)
print(a == None, None == a, a != None, None != a)
print([a] == [b], b in [a], a in [a])


class Child(Equal):
    def __eq__(self, other: object):
        print("child eq", self.name)
        return NotImplemented

    def __gt__(self, other: object):
        print("child gt", self.name)
        return NotImplemented


def compare(a: Equal, b: Equal) -> None:
    print(a == b, a != b, a < b)


compare(Equal("base", True), Child("child", False))


class Neither:
    def __eq__(self, other: object):
        print("Neither.eq")
        return NotImplemented

    def __ne__(self, other: object):
        print("Neither.ne")
        return NotImplemented


x = Neither()
y = Neither()
print(x == x, x != x, x == y, x != y)
