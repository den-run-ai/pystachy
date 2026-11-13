# a != b by __eq__ where the class has no __ne__, and by a __ne__ that returns NotImplemented:
# after both operands' methods, the objects' identity decides.
class OnlyEq:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        print("OnlyEq.__eq__", self.n)
        if not isinstance(other, OnlyEq) or self.n < 0:
            return NotImplemented
        return self.n == other.n


class Both:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        print("Both.__eq__", self.n)
        if not isinstance(other, Both):
            return NotImplemented
        return self.n == other.n

    def __ne__(self, other):
        print("Both.__ne__", self.n)
        if not isinstance(other, Both) or self.n < 0:
            return NotImplemented
        return self.n != other.n


a = [OnlyEq(1), OnlyEq(1), OnlyEq(-1), OnlyEq(-1)]
print(a[0] != a[1], a[0] == a[1])
print(a[2] != a[3], a[2] == a[3])
print(a[2] != a[2], a[2] == a[2])
print(a[0] != a[2], a[2] != a[0])
b = [Both(1), Both(2), Both(-1), Both(-1)]
print(b[0] != b[1], b[0] == b[1])
print(b[2] != b[3], b[2] != b[2], b[2] == b[3])
print(b[0] != a[0], a[0] != b[0], b[0] == a[0])
