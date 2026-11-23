# error: expected M, got str (making the table of str as object (for M != its object), converted at tests/errors/classes/object_ne_dict_own.py:11; M.__ne__() takes only M, where CPython calls it with any value that a value of object holds: annotate its parameter object and narrow it with isinstance())
# a class deriving from dict whose __ne__ is annotated to take only its own class, stored as object
# beside a str: CPython calls the method for != with the str, which it cannot take, so the program
# is rejected rather than answered by dict's comparison
class M(dict[str, int]):
    def __ne__(self, other: "M") -> bool:
        return False


x: object = M()
y: object = ""
print(x != y)
