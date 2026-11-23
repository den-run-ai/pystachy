# error: expected M, got int | None (making the table of int | None as object (for M == its object), converted at tests/errors/classes/object_eq_dict_own.py:15; M.__eq__() takes only M, where CPython calls it with any value that a value of object holds: annotate its parameter object and narrow it with isinstance())
# a class deriving from dict whose __eq__ is annotated to take only its own class, stored as object
# beside an int: CPython calls the method with the int (reflected, the int's own __eq__ declining),
# which it cannot take, so the program is rejected rather than answered by dict's comparison
class M(dict[str, int]):
    def __eq__(self, other: "M") -> bool:
        return len(self) == len(other)


def same(a: object, b: object) -> bool:
    return a == b


x: object = M()
y: object = 5
print(same(y, x))
