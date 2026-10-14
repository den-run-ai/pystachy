# error: multiple inheritance is not supported: a class may have only one base
class A:
    pass


class B:
    pass


class C(A, B):
    pass
