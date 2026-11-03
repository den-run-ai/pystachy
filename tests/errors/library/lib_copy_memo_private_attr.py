# error: _memo_get() is lib/copy.py's own: it reads a deep copy's memo back as the original's type
# The memo's helpers are names of module copy too (it imports them), which another module may not
# call either
import copy


class A:
    def __init__(self) -> None:
        self.n = 4


m = copy._Memo()
got = copy._memo_get(m, A())
print(got is None)
