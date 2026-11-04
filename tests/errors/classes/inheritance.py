# error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base
class A:
    field: int = 0


class B:
    other: int = 1


class C(A, B):
    pass
