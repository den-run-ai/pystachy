# error: exc_eq_subclass_narrow.py:14: error: __eq__() of F cannot compare an operand of type E
# x and y may be objects of F, whose __eq__ CPython calls with an E whatever its annotation
# says: rejected, as between objects of ordinary classes (CPython prints False True)
class E(Exception):
    pass


class F(E):
    def __eq__(self, other: "F") -> bool:
        return True


def same(x: E, y: E) -> bool:
    return x == y


print(same(E("a"), E("b")), F("a") == F("b"))
