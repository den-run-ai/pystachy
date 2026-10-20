# A field that __init__ types int, given an int and then a str by a template's method:
# int | str.
class S:
    def __init__(self, w: int) -> None:
        self.w = w

    def setw(self, v):
        self.w = v


s = S(1)
s.setw(2)
print(repr(s.w))
s.setw("x")
print(repr(s.w))
