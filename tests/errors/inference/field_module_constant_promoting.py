# error: cannot infer the type of field 'big'
# A constant of a module whose ints promote (# pystachy: python-int) does not type a field: its
# value's spelling does not give the global's type there
from bigconsts import BIG


class Holder:
    def __init__(self) -> None:
        self.big = BIG


print(Holder().big)
