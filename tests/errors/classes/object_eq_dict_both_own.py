# error: expected M, got int | None (making the table of int | None as object (for M == its object), converted at tests/errors/classes/object_eq_dict_both_own.py:18; M.__eq__() takes only M, where CPython calls it with any value that a value of object holds: annotate its parameter object and narrow it with isinstance())
# a class deriving from dict with __eq__ and __ne__ annotated to take only its own class, stored as
# object beside an int: CPython calls its __eq__ with the int, which it cannot take, so the program
# is rejected rather than answered by dict's comparison
class M(dict[str, int]):
    def __eq__(self, other: "M") -> bool:
        return True

    def __ne__(self, other: "M") -> bool:
        return False


def same(a: object, b: object) -> bool:
    return a == b


x: object = M()
y: object = 5
print(same(x, y), x != y)
