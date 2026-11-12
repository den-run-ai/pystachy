# error: inheritance_trait_roots.py:28: error: traits A and B of one class derive from different classes of its primary base's chain, Root and Mid: not supported
# Traits of one class derive from one class of its primary base's chain: A from Root and B
# from Mid would put A before Mid in CPython's method resolution order (Both, Primary, A, B, Mid,
# Root), so A.f, not Mid.f, would be Both's.
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


class Both(Primary, A, B):
    pass


print(Both().f())
