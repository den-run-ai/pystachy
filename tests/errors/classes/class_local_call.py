# error: class_local_call.py:13: error: local variable 'A' is read before its first assignment; declare it first (A: T)
# A function that assigns A makes A its local, so a read of A further up is no read of the class A
# (CPython raises UnboundLocalError there): A.f() through the class is such a read, as A() is.
class A:
    @staticmethod
    def f() -> int:
        return 1


def g() -> None:
    x = 0
    print(x)
    x = A.f()
    A = 5
    print(x, A)


g()
