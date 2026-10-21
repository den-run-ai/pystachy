# error: reflect_setattr_runtime_fit.py:12: error: setattr() of a run-time name with a str is not supported: the name may be P's field x, a int
# The value must fit every slot a run-time name may name: a run-time check would raise where CPython does not
class P:
    __slots__ = ("x", "s")

    def __init__(self) -> None:
        self.x = 1
        self.s = "a"


p = P()
setattr(p, input(), "b")
print(p.s)
