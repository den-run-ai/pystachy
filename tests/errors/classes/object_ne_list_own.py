# error: expected L, got int | None (making the table of int | None as object (for L != its object), converted at tests/errors/classes/object_ne_list_own.py:16; L.__ne__() takes only L, where CPython calls it with any value that a value of object holds: annotate its parameter object and narrow it with isinstance())
# a class deriving from list whose __ne__ is annotated to take only its own class, stored as object
# beside an int: CPython calls the method for != with the int, which it cannot take, so the program
# is rejected rather than answered by list's comparison (object_eq_builtin_ne.py: one that takes
# object)
class L(list[int]):
    def __ne__(self, other: "L") -> bool:
        return len(self) != len(other)


def differ(a: object, b: object) -> bool:
    return a != b


x: object = L()
y: object = 5
print(differ(x, y), differ(y, x))
