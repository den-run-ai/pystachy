# error: expected L, got str (making the table of str as object (for L != its object), converted at tests/errors/classes/object_eq_list_both_own.py:18; L.__ne__() takes only L, where CPython calls it with any value that a value of object holds: annotate its parameter object and narrow it with isinstance())
# a class deriving from list with __eq__ and __ne__ annotated to take only its own class, stored as
# object beside a str and compared with != only: CPython calls its __ne__ with the str, which it
# cannot take, so the program is rejected rather than answered by list's comparison
class L(list[int]):
    def __eq__(self, other: "L") -> bool:
        return len(self) == len(other)

    def __ne__(self, other: "L") -> bool:
        return len(self) != len(other)


def differ(a: object, b: object) -> bool:
    return a != b


x: object = L()
y: object = ""
print(differ(y, x))
