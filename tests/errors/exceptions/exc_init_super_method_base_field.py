# error: C.__init__ may leave field 's' of B unassigned where it is read: assign it, or call super().__init__(...) first
class B(Exception):
    def __init__(self) -> None:
        self.s = "x"

    def m(self) -> int:
        return len(self.s)


class C(B):
    def __init__(self) -> None:
        try:
            print(super().m())
        except AttributeError as e:
            print("AttributeError:", e)
        super().__init__()


C()
