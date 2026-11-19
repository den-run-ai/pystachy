# error: inheritance_trait_roots_inherited.py:32: error: traits A and B of one class derive from different classes of its primary base's chain, Root and Mid: not supported
# The traits of a class include those of its primary base: First's A derives from Root and Both's
# B from Mid, which CPython's method resolution order puts between them (Both, First, Primary, B,
# Mid, A, Root), as it does for two traits of one class statement (inheritance_trait_roots).
class Root:
    def f(self) -> int:
        return 0


class Mid(Root):
    def f(self) -> int:
        return 1


class Primary(Mid):
    pass


class A(Root):
    def f(self) -> int:
        return 2


class B(Mid):
    pass


class First(Primary, A):
    pass


class Both(First, B):
    pass


print(Both().f())
