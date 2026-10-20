# The text of getattr(o, name) for a run-time name: a class's __doc__ as CPython 3.13's compiler
# keeps a docstring (its lines' common indentation removed), and __static_attributes__, the
# sorted names stored as self.x (the name self) by an assignment or an annotated one with a
# value (also in nested functions); not by += or through another name
class P:
    """
    Multi-line docstring.
        Indented line.
    """

    def __init__(self) -> None:
        self.x = 1
        self.o = 0
        self.c: int = 2
        self.x += 1
        self.k = 0
        self.g = 0

    def m(self) -> None:
        def inner() -> None:
            self.g = 1

        inner()

    def other(me) -> None:
        me.o = 1

    def more(self) -> None:
        self.k += 1


class Q(P):
    def __eq__(self, other: object) -> bool:
        return True


for n in input().split():
    print(n, repr(getattr(P(), n)))
    print(n, getattr(Q(), n))
