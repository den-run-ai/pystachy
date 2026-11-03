# error: _memo_put() is lib/copy.py's own: it reads a deep copy's memo back as the original's type
# Nor may another module take one of the memo's helpers as a value, to call it through that
import copy


class A:
    def __init__(self) -> None:
        self.n = 4


put = copy._memo_put
put(copy._Memo(), A(), A())
print("stored")
