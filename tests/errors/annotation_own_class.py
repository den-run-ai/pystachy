# error: name 'Pair' is not defined (CPython evaluates this annotation when the def statement runs
class Pair:
    def __init__(self, a: int):
        self.a = a

    def same(self, other: Pair) -> bool:
        return self.a == other.a


print(Pair(1).same(Pair(1)))
