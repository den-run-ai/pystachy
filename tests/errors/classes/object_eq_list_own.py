# error: expected L, got str (making the table of str as object (for L == its object), converted at tests/errors/classes/object_eq_list_own.py:15; L.__eq__() takes only L, where CPython calls it with any value that a value of object holds: annotate its parameter object and narrow it with isinstance())
# a class deriving from list whose __eq__ is annotated to take only its own class, stored as object
# beside a str: CPython calls the method with the str, which it cannot take, so the program is
# rejected rather than answered by list's comparison (object_eq_builtin_ne.py: one that takes object)
class L(list[int]):
    def __eq__(self, other: "L") -> bool:
        return len(self) == len(other)


def same(a: object, b: object) -> bool:
    return a == b


x: object = L()
y: object = ""
print(same(x, y), same(y, x))
