# error: expected F, got str (making the table of str as object (for F == its object), converted at tests/errors/classes/object_eq_strict.py:14; F.__eq__() takes only F, where CPython calls it with any value that a value of object holds: annotate its parameter object and narrow it with isinstance())
# an __eq__ annotated to take only its own class, which CPython calls with whatever value of object
# it is compared with, is compiled for each type of value that object holds: one it cannot take
# rejects the program (object_eq_pairs.py: an __eq__ that takes object)
class F:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: "F") -> bool:
        return other.v == self.v


def main() -> None:
    values: list[object] = [F(1), "text"]
    print(values[0] == values[1])


main()
