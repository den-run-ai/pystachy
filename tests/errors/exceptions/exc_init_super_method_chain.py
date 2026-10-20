# error: C.__init__ may leave field 's' of B unassigned where it is read: assign it, or call super().__init__(...) first
class A(Exception):
    def __init__(self) -> None:
        self.s = "x"

    def n(self) -> int:
        return len(self.s)


class B(A):
    def m(self) -> int:
        return super().n()


class C(B):
    def __init__(self) -> None:
        try:
            print(super().m())
        except AttributeError as e:
            print("AttributeError:", e)
        super().__init__()


C()
