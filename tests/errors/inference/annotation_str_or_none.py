# error: annotation_str_or_none.py:10: error: unsupported operand type(s) for |: 'str' and 'NoneType'
# A def evaluates its annotations when it runs: "C" | None is str | None, a TypeError there
# (the whole annotation can be a string: "C | None").
class C:
    def __init__(self, v: int) -> None:
        self.v = v


# (it compiled as C | None and printed 3)
def f(x: "C" | None) -> int:
    return 0 if x is None else x.v


print(f(C(3)))
